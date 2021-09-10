# Motorcycle ads aggregator

Command line Python script that collects motorcycle advertisement details from listing websites.

## Usage
```shell
python aggregator.py [--limit=n]
```
`--limit=n` optional argument where `n` is a positive number.

## Installation
Installation consists of setting up the database, configuration file
and installing dependencies.
### 1. Setting up the database
The script saves the details of each listing to a mysql database, therefore
you should have a mysql server set up and running before running this
script and perform the following tasks.

1. Create a database with any preferred name *e.g. motorcycle_db*
2. Create a user and password that at least has `SELECT` and `INSERT` 
privileges for the above database
3. Import the provided **motorcycle_db.sql** file into the database

### 2. config.json
A json file named **config.json** should be in the application root directory
with the following settings.

The entries `DATABASE_NAME`, `USERNAME`, `PASSWORD` and `HOSTNAME`
are **required**. Other entries are optional, but you may find them helpful.
```json
{
  "FETCH_LIMIT": 10,
  "WAIT_SECONDS": 3,
  "MAX_FAILS": 2,
  "DATABASE_NAME": "",
  "USERNAME": "",
  "PASSWORD": "",
  "HOSTNAME": "",
  "PROXIES": {
    "HTTPS": "",
    "HTTP": ""
  },
  "USER_AGENT": ""
}
```

### 3. Install Dependencies
Use Python 3.8.11 or newer version to run the script

Use a package manager such as [pip](https://pip.pypa.io/en/stable/) to install the following packages.
- [requests 2.26.0](https://pypi.org/project/requests/)
- [mysql-connector-python 8.0.26](https://pypi.org/project/mysql-connector-python/)

Alternatively you can install the dependencies using the provided
**requirements.txt** using the following pip command
```bash
pip install -r requirements.txt
```

