# Jira Report

Generate a monthly `.xls` report of [Jira](https://jira.atlassian.com/) tasks assigned to me.

## Prerequisites

Install [poetry](https://poetry.eustace.io/):

```shell
$ curl -sSL https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py | python
```

## Installation

Install the module after download:

```shell
$ poetry install
```

## Configuration

Create a Jira API Token:

1. Go to your Jira account settings.
2. Open Security.
3. Click *[Create and manage API tokens](https://id.atlassian.com/manage-profile/security/api-tokens)*.
4. Create a new API token.
5. Copy the token to clipboard.

Create a local `.env` file with the following environment variables:

```shell
$ echo 'GITHUB_USERNAME="szabadaba"' >> .env
$ echo 'GITHUB_REPO="jdoe/mycompany"' >> .env
$ echo 'GITHUB_TOKEN="qeYEtFiNUJ8FCSEbBp25jNKc"' >> .env
$ echo 'JIRA_SERVER_URL="https://mycompany.atlassian.net"' >> .env
$ echo 'JIRA_USERNAME="jdoe@mycompany.com"' >> .env
$ echo 'JIRA_API_TOKEN="qeYEtFiNUJ8FCSEbBp25jNKc"' >> .env
```


## Usage

The command:

```shell
$ poetry run jira-report [--start YYYY/MM] [--end YYY/MM] [--force-overwrite]
```

### Example #1

Generate a report for the current month:

```shell
$ poetry run jira-report
```

### Example 

```shell
$ poetry run jira-report --start 2019/01 --end 2019/12 -f
```
