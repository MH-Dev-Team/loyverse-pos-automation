# Daily Sales Summary Automation

This program will submit summary of sales data according to KL East Mall Management requirement.

It will extract daily sales data from Loyverse POS system then send a sale file exported to the mall server by schedule after outlet closure. The program integrate with Loyverse POS system through API.

Read more about Loyverse API documentation: https://developer.loyverse.com/docs/


### What will this program do

1. Extract sale data from Loyverse POS system and do the necessary calculation to come out with the Gross Sale Amount as specified by the mall specifiction
2. Create a sale file as txt file based on the mall format for file name and content
3. Send the sale file to mall server via sFTP
4. Automate the process in a daily basis after outlet closure.

### Requirements

This project is utilizing Python >=3.10.

### Web application setup

You can follow prerequisite server setup from **GUIDE.pdf** file.

Content of **.env** file would be secret parameters for accessing Loyverse POS system via their API as well as mall sFTP username and password. Then paste all secret keys to **.env** file.

A bash script **run.sh** should be run according to schedule by cronjob. Content of **run.sh**:

```
#!/bin/bash
python3 /home/loyverse/webapps/loyverse-pos-automation/app.py -s
```

### Dependencies installation

Add SSH configuration in RunCloud, more instruction: https://runcloud.io/docs/connect-to-server-via-ssh. Access remote server from local PC terminal using SSH (`hostname` is typically server's IP address).

```
ssh loyverse@hostname
```

Change directory and look at project files.

```
cd webapps/loyverse-pos-automation/
ls -la
```

Install all Python dependencies from **requirements.txt** file.

```
pip install -r requirements.txt
```

Test if Loyverse API is working well (without saving sale file result).

```
python3 app.py
```

The result would be something like this:

```
2024-04-11 11:51:54 [INFO] export G245A|11042024|0.00 to G245A_11042024.txt
2024-04-11 11:51:54 [INFO] delete G245A_11042024.txt in localpath
```

### Usage

General usage without saving sale file result on working directory:

```
python3 app.py
```

Program help:

```
python3 app.py -h

usage: app.py [-h] [--date [YYYY-MM-DD]] [-k] [-s]

Daily sales data submission program

options:
  -h, --help           show this help message and exit
  --date [YYYY-MM-DD]  manual defining date, default is today
  -k, --keep           do not remove sale file after submit
  -s, --submit         submit sale file to mall's server

```
