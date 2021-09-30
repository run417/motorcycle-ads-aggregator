# Motorcycle ads aggregator

Command line Python script that collects motorcycle advertisement details from listing websites. Supports the following
sites:

- Ikman
- Riyasewana

## Usage

In the command line run the file `aggregator.py` using python.

```shell
python aggregator.py [-L integer] [-N]
```

The `-L` option limits the number of ads fetched. The number provided should be a positive number. Value `0` means that
there is no limit.

The `-N` option will fetch only new ads. An ad is considered 'new' when it is not present in the local database and is
posted later than the latest ad in the local database.

Any option when specified in the command line will override that option if it is also specified in the `config.json`
file.

## Installation

Installation consists of setting up the database, configuration file and installing dependencies.

### 1. Setting up the database

The script saves the details of each listing to a mysql database, therefore you should have a mysql server set up and
running before running this script and perform the following tasks.

1. Create a database with any preferred name *e.g. motorcycle_db*
2. Create a user and password that at least has `SELECT` and `INSERT`
   privileges for the above database
3. Import the provided **motorcycle_db.sql** file into the database

### 2. config.json

A json file named **config.json** should be in the application root directory with the following settings.

The entries `DATABASE_NAME`, `USERNAME`, `PASSWORD`, `HOSTNAME`, and `SOURCES` are **required**.

Other entries are optional, but defaults values will be used in script.

```json
{
  "WAIT_SECONDS": 3,
  "MAX_FAILS": 2,
  "DATABASE_NAME": "motorcycle_db",
  "USERNAME": "",
  "PASSWORD": "",
  "HOSTNAME": "",
  "PROXIES": {
    "HTTPS": "",
    "HTTP": ""
  },
  "USER_AGENT": "",
  "SOURCES": [
    {
      "name": "ikman",
      "limit": 10,
      "fetch_type": "all"
    },
    {
      "name": "riyasewana",
      "limit": 10,
      "fetch_type": "new"
    }
  ]
}
```

Each **source** is a `json` object with three properties. `name`, `limit`, `fetch_type`

The `name` property must be one of the following supported sources

- ikman
- riyasewana

The `limit` property of a source must be a positive number. `0` will fetch every ad it can find in a session.

The `fetch_type` must be `new` or `all`

The `WAIT_SECONDS` property is the number of seconds to wait between http requests.

The `MAX_FAILS` property is the number of errors the script can tolerate. The types of tolerable errors are http errors
and parsing errors.

If you want to fetch ads from a single source only then you must remove the other sources completely with all its
options. E.g. If you want to fetch ads only from *ikman* the sources section should look like the following:

```json
{
  "SOURCES": [
    {
      "name": "ikman",
      "limit": 10,
      "fetch_type": "all"
    }
  ]
}
```

### 3. Install Dependencies

Use Python 3.8.11 or newer version to run the script

Use a package manager such as [pip](https://pip.pypa.io/en/stable/) to install the following packages.

- [requests 2.26.0](https://pypi.org/project/requests/)
- [mysql-connector-python 8.0.26](https://pypi.org/project/mysql-connector-python/)
- [beautifulsoup 4.10.0](https://pypi.org/project/beautifulsoup4/)

Alternatively you can install the dependencies using the provided **requirements.txt** (much easier) using the following
pip command

```bash
pip install -r requirements.txt
```

