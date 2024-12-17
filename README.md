# Cross Country Course Comparisons
## Description
This repository contains files that can be used for the scraping and analyzing of results data from cross country races. The files allow for direct comparison of two races based on results from runners who competed in both. It then uses the comparison capability to allow the user to standardize courses of varying difficulty and to run virtual meets. To learn more about the motivation behind this project, the data of interest, and our methods, read "Course_Comparison_Project_Proposal.pdf". 

## Quick Start Guide
We did not include any pipenv setup files for this, so ensure that the necessary libraries (`pip install pandas numpy beautifulsoup4 as bs4 requests`) are installed.

To interact with the dashboard:
* Download `courses.py`, `courses.db` and `dash_testing.py` to the same folder. Do not rename any files.
* Navigate to the directory where the files are located via the command line (example: `cd '/Users/anniewicker/Desktop/23-24/Fall_24/Automation'`).
* Type `python dash_testing.py`. A link like this should appear in the output: http://127.0.0.1:8050/.
* Paste link into your browser to see the dashboard. 

To just see an example of the database and the querying functions in a Jupyter environment:
* Download `courses.py` and `CourseFunctions.ipynb` in the same folder.
* Follow the instructions in the notebook to create the database, load the data, and see the querying functions in action. 

All data loaded into this database will come from individual race pages on the TFRRS website. Links to these pages can be found at https://www.tfrrs.org/. To load a race or races of interest, copy the results URL from TFRRS and paste it into the "Enter Race URL" box on the dashboard. Click "Scrape and Load Results" to load the data. To compare courses or predict times, a minimum of two races must be loaded in the dashboard. The sample database in this repository is pre-loaded with seven race results. 

## Files
`courses.db` is a pre-constructed sample database. Those unfamiliar with TFRRS results can download the database to explore the dashboard without any specific races in mind. Races of interest can be added via the dashboard. 

`courses.py` creates and maintains a database of all user-inputted TFRRS data. It incorporates a webscraping script to load the data into the database, and contains functions for running queries on the database. Each function in `courses.py` is accompanied by a docstring. 

`CourseFunctions.ipynb` provides a sample use of the database in its full functionality. This file contains example outputs of all the functions being run on a database with loaded races. 

`dash_testing.py` contains code for an interactive app built using Dash. 
