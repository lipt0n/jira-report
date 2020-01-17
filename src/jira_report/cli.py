#!/usr/bin/env python

"""
Generate a monthly .xls report of Jira tasks assigned to me.

Usage:
$ poetry run jira-report [--month 2019/10] [--days 21] [--force-overwrite]

Configuration:
$ echo 'JIRA_SERVER_URL="https://mycompany.atlassian.net"' >> .env
$ echo 'JIRA_USERNAME="jdoe@mycompany.com"' >> .env
$ echo 'JIRA_API_TOKEN="qeYEtFiNUJ8FCSEbBp25jNKc"' >> .env

Interactive prompt appears if a local .env file is missing.
"""
from difflib import SequenceMatcher

import argparse
import calendar
import datetime
import logging
import os
from typing import Any, Dict, List, Optional

import dateutil.parser
import environs
import jira
import workdays
import xlwt
from github import Github, PullRequest

logging.basicConfig(format='[%(levelname)s] %(message)s', level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def run() -> None:
    """Command wrapper for Poetry."""
    try:
        main(parse_args())
    except KeyboardInterrupt:
        LOGGER.warning('Aborted')


def main(args: argparse.Namespace) -> None:
    """Script entry point."""

    title = args.date.strftime("%Y_%m-")+args.date2.strftime("%Y_%m")
    filename = f'Jira_{title}.xls'

    if os.path.exists(filename) and not args.force_overwrite:
        LOGGER.error('File already exists: "%s", use the -f flag to overwrite', filename)
    else:
        api = jira.JIRA(**jira_config())
        issues = find_issues(args.date, args.date2,api)
        pullrequests = find_pullrequests(github_config(), args.date, args.date2)
        if len(issues) > 0:
            LOGGER.info('Found %d tasks assigned to you during that period.', len(issues))
            xls_export(issues, pullrequests, month_hours(args.date, args.business_days), title, filename,api)
        else:
            LOGGER.info('There were no tasks assigned to you during that period.')


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""

    def parse_month(text: str) -> datetime.date:
        """Return a datetime instance."""
        return datetime.datetime.strptime(text, '%Y/%m').date()

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--force-overwrite', action='store_true', default=False)
    parser.add_argument('-d', '--days', dest='business_days', type=int)
    parser.add_argument('--start',
                        metavar='YYYY/MM',
                        dest='date',
                        type=parse_month,
                        default=datetime.date.today())
    parser.add_argument('--end',
                        metavar='YYYY/MM',
                        dest='date2',
                        type=parse_month,
                        default=datetime.date.today())
    return parser.parse_args()


def github_config() ->  Dict[str, str]:
    environs.load_dotenv()

    load_var('GITHUB_TOKEN')
    return {
        'token': os.getenv('GITHUB_TOKEN'),
        'username': os.getenv('GITHUB_USERNAME'),
        'repo': os.getenv('GITHUB_REPO')
    }

def jira_config() -> Dict[str, str]:
    """Return a dict of Jira configuration options."""

    environs.load_dotenv()

    load_var('JIRA_SERVER_URL')
    load_var('JIRA_USERNAME')
    load_var('JIRA_API_TOKEN')

    return {
        'server': os.getenv('JIRA_SERVER_URL'),
        'basic_auth': (os.getenv('JIRA_USERNAME'), os.getenv('JIRA_API_TOKEN'))
    }


def load_var(name: str) -> None:
    """Ensure that Jira configuration is stored in .env file."""
    if name not in os.environ:
        prompt = ' '.join([x.title() for x in name.split('_')]) + ': '
        while True:
            value = input(prompt)
            if value.strip() != '':
                break
        with open('.env', 'a') as file_object:
            print(f'{name}="{value}"', file=file_object)
        environs.load_dotenv()

def find_pullrequests(config: Dict[str, str], date: datetime.date,date2: datetime.date):
    g = Github(config['token'], per_page=100)
    repo = g.get_repo(config['repo'])
    pulls = repo.get_pulls(state='closed', sort='created')
    LOGGER.info('get PRs from github (%d)', pulls.totalCount)
    l = []
    for i, pr in enumerate(pulls):
        if i%101 == 0 :
            LOGGER.info(f"{i}/{pulls.totalCount} loaded")
        if pr.user.login == config['username'] and date <= pr.created_at.date() <= date2:
            l.append(pr)
    LOGGER.info(' (%d) for user %s', pulls.totalCount, config['username'])
    return l


def find_issues(date: datetime.date,date2: datetime.date, api) -> jira.client.ResultList:
    """Return a list of Jira issues for the given month."""
    logging.info('Querying Jira...')
    
    r = []
    for i in range(3):
        r.extend(api.search_issues(jql(date, date2), expand='changelog', maxResults=100, startAt=0+i*100))

    return r


def jql(date: datetime.date, date2: datetime.date) -> str:
    """Return a JQL query to get issues assigned to me in the given month."""
    start_date = f'{date.year}/{date.month:02}/01'
    end_date = f'{date2.year}/{date2.month:02}/{month_days(date2):02}'
    LOGGER.info(f'assignee was currentUser() DURING ("{start_date}", "{end_date}") ORDER BY created ASC')
    return f'assignee was currentUser() DURING ("{start_date}", "{end_date}") ORDER BY created ASC'


def month_days(date: datetime.date) -> int:
    """Return the number of days in the given month."""
    _, num_days = calendar.monthrange(date.year, date.month)
    return num_days


def month_hours(date: datetime.date, business_days: Optional[int]) -> int:
    """Return the number of work hours in the given month."""

    if business_days is None:
        start_date = datetime.date(date.year, date.month, 1)
        end_date = datetime.date(date.year, date.month, month_days(date))
        business_days = workdays.networkdays(start_date, end_date)

    LOGGER.info('Business days=%d (%d hours)', business_days, business_days * 8)

    return business_days * 8
def get_pr(issue:str, pullrequests: List[PullRequest.PullRequest]):
    names = [issue, '-'.join(issue.split('_'))]
    if len(issue.split("_"))>1 :
        names.append(issue.split("_")[1])
    if len(issue.split("-"))>1 :
        names.append(issue.split("-")[1])
    if len(issue.split("FLIP"))>1 :
        names.append(issue.split("FLIP")[1])
    
    for name in names:
        
        for pr in pullrequests:
            if pr.title.lower().find(name.lower()) != -1 or pr.head.ref.lower().find(name.lower())!=-1:
                LOGGER.info(f"[{issue}] -> [{name}]     in    [{pr.title}][{pr.head.ref.lower()}]  ")
                LOGGER.info(f"---------------------------------------------------------")    
                return pr
            
def find_issues_for_pr(pr: PullRequest.PullRequest, issues: List[jira.Issue] ):
    find_in = f"{pr.title} {pr.body} {pr.head.ref}".lower()
    results = []
    k = set()
    for i in issues:     
        if find_in.find(i.key.lower()) != -1 and i.key not in k:
            results.append(i)
            k.add(i.key)
        if find_in.find("".join(i.key.lower().split('-')) ) != -1 and i.key not in k:
            results.append(i)
            k.add(i.key)
        if find_in.find("_".join(i.key.lower().split('-')) ) != -1 and i.key not in k:
            results.append(i)
            k.add(i.key)
        if find_in.find(i.key.lower().split('-')[1]+' ' ) != -1 and i.key not in k:
            results.append(i)
            k.add(i.key)
        if find_in.find(" ".join(i.key.lower().split('-')[1]) ) != -1 and i.key not in k:
            results.append(i)
            k.add(i.key)
    if len(results)==0:  
        # now its time for something more fancy
        for i in issues: 
            name = i.fields.summary.lower()
            prname = pr.title.lower()
            if SequenceMatcher(None, name, prname).ratio() > 0.75 :
                results.append(i)
                return results
    if len(results)==0:  
        # still nothing? dont be so picky
        for i in issues: 
            name = i.fields.summary.lower()
            prname = pr.title.lower()
            if SequenceMatcher(None, name, prname).ratio() > 0.5 :
                results.append(i)
                return results
    if len(results)==0:  
        # fuck it , gimme something
        for i in issues: 
            name = i.fields.summary.lower()
            prname = pr.title.lower()
            if SequenceMatcher(None, name, prname).ratio() > 0.25 :
                results.append(i)
                return results
    if len(results)==0:
        LOGGER.warning(f"nothing for: {find_in}")
    return results
        

def get_issue_dates(issue: jira.Issue, api):
    date_from = ''
    date_to = ''
    for history in issue.changelog.histories:
            date_from = date_from = dateutil.parser.parse(history.created).replace(tzinfo=None)
            for item in history.items:

                if item.field == 'status' and item.toString == 'Done':
                    date_to = dateutil.parser.parse(history.created).replace(tzinfo=None)
                if item.field == 'status' and ( item.toString == 'In Progress' or item.toString == 'To Do' ):
                    date_from = dateutil.parser.parse(history.created).replace(tzinfo=None)

    return date_from, date_to



def xls_export(issues: List[jira.Issue],
                pullrequests: List[PullRequest.PullRequest],
               hours: int,
               title: str,
               filename: str, api) -> None:
    """Save Jira issues to a spreadsheet file."""

    class Styles:
        """A class whose attributes represent different styles."""

        bold = xlwt.easyxf('font: bold on; align: vert centre')
        middle = xlwt.easyxf('align: vert centre')

        date_format = xlwt.easyxf('align: vert centre, horiz left')
        date_format.num_format_str = 'yyyy-mm-dd'

        hours_format = xlwt.easyxf('align: vert centre, horiz right')
        hours_format.num_format_str = '#,#0.0 "h"'
        h = xlwt.easyxf('pattern: pattern solid, fore_colour dark_blue;'
                              'font: colour white, bold True;')
        hd = xlwt.easyxf('pattern: pattern solid, fore_colour dark_blue;'
                              'font: colour white, bold True;')
        hd.num_format_str = 'yyyy-mm-dd'

        invisible = xlwt.easyxf('align: vert centre; font: color white')

    workbook = xlwt.Workbook(encoding='utf-8')
    sheet = workbook.add_sheet(title)

    row_height = sheet.row_default_height = 450

    column_headers = (


        'Created at', #0
        'Closed at', #1
        'Branch / id', #2
        'Title', #3
        
        'Link', #4
        'Description' #5
        
    )

    styles = Styles()

    for column, header in enumerate(column_headers):
        write(sheet, 0, column, header, styles.bold)
        sheet.row(0).height = row_height
        # sheet.col(5).width = 300000
    row = 1
    for  pr in pullrequests:
        

        sheet.row(row).height = row_height


        issues_for_pr =  find_issues_for_pr(pr, issues)
        start_issue = pr.created_at
        for issue in issues_for_pr:
            start_date, end_date = get_issue_dates(issue, api)
            if type(start_date) is datetime and start_date.date() < start_issue :
                start_issue = start_date.date() 
            else:
                print("type(start_date) is datetime ", type(start_date) is datetime )
                print(start_date)

        write(sheet, row, 0, start_issue , styles.hd)
        write(sheet, row, 1, pr.closed_at , styles.hd)
        write(sheet, row, 2, pr.head.ref, styles.h) # branch
        write(sheet, row, 3, pr.title , styles.h)
        # write(sheet, row, 4, pr.body , styles.h)
        write(sheet, row, 4, f"https://github.com/Bomoda/bomoda2/pull/{pr.id}", styles.h)
        for issue in issues_for_pr:
            row +=1
            description = issue.fields.description
            if not description:
                description = pr.body
            if len(description) > 1000:
                description = description[:1000] + ' ...'

            start_date, end_date = get_issue_dates(issue,api)
            write(sheet, row, 0, start_date, styles.date_format)
            write(sheet, row, 1, end_date, styles.date_format)
            write(sheet, row, 2, issue.key, styles.middle)
            write(sheet, row, 3, issue.fields.summary, styles.middle)
            # write(sheet, row, 5, description, styles.middle)
            sheet.write(row, 5, description, styles.middle)
           
            write(sheet, row, 4, make_link(issue.permalink()), styles.middle)
        row+=2
        



    workbook.save(filename)
    logging.info('Exported file: "%s"', os.path.join(os.getcwd(), filename))


def write(sheet: xlwt.Worksheet, row: int, col: int, value: Any, style: xlwt.XFStyle) -> None:
    """Write text to a cell and auto-fit the column width."""

    sheet.write(row, col, value, style)

    char_width = 256
    text_width = len(str(value)) * char_width

    column = sheet.col(col)
    if column.get_width() < text_width:
        column.set_width(text_width)


def make_datetime(text: str) -> datetime.datetime:
    """Return an offset-naive datetime from an ISO-8601 string."""
    return dateutil.parser.parse(text).replace(tzinfo=None)


def make_link(url: str) -> xlwt.Formula:
    """Return an interactive hyperlink formula."""
    return xlwt.Formula(f'HYPERLINK("{url}")')


def story_points(issue: jira.Issue) -> Optional[float]:
    """Return the number of story points of None."""
    try:
        return issue.fields.customfield_10020
    except AttributeError:
        logging.warning('No story points assigned to %s', issue.key)
        return None


def hours_worked(row: int, issues: List) -> xlwt.Formula:
    """Return a math formula to calculate the number of hours worked on an issue."""
    return xlwt.Formula(f'H{row + 1}/SUM(H2:H{len(issues) + 1})*H1')
