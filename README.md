# Cross Country Course Comparisons
## Description
This repository contains files that can be used for the scraping and analyzing of results data from cross country races. Ultimately, the files will enable a user to run virtual meets, standardize courses of varying difficulty, and track runner improvement throughout the season.

## Getting Started
The `tffrsdatascraping.py` is the standalone web scraping function. It takes a URL from the Track and Field Results Reporting System (TFRRS) and scrapes the data from that race. The function defaults to scraping women's results, but the 'gender' argument can be changed to gender=men for men's results. It automatically drops racers' times who did not start (DNS) or did not finish (DNF) the race. 

`courses.py` creates and maintains a database of all user-inputted TFRRS data. It incorporates the webscraping script to load the data into the database, and contains functions for running queries on the database. `see_loaded_races` allows the user to check which races have been loaded into the database. `course_lookup` and `runner_lookup` allow a user to input part of a course's or runner's name to find all the records that match that snipit. Because one course can host multiple races, the `course_lookup` function is especially useful for users who want to compare times on the same course at different points in a season. `find_races_in_common` is a function that takes two unique runner IDs as inputs and outputs all of the races that those two runners have run in together. The `compare_two_courses` function takes two unique race IDs as inputs, and returns the difference in average time and the time ratio between two races, as well as the number of runners in common between the two. This function only compares races with **at least one** runner in common. 

`CourseFunctions.ipynb` provides a sample use of the database in its full functionality. This file contains example outputs of all the functions being run on a database with loaded races. 

## Using the Program

Begin by downloading both the `courses.py` file and the `CourseFunctions.ipynb` notebook in the same folder. The `courses.py` file contains the functions which allow the user to create and query the database, but all commands to access this code will be run from the `CourseFunctions.ipynb` notebook. Load the necessary libraries by running the first two blocks of code, then initialize the database by running the third block with the 'create' argument set to True. After initializing the database, run the next block of code to create the tables. You are now ready to begin loading data into the database.

All data loaded into this database will come from individual race pages on the TFRRS website. Links to these pages can be found at https://www.tfrrs.org/. Begin entering data into the database by running the `db.load_results` function with a race page URL for each race you would like to load into the database. You should only run the code once for each URL, otherwise an error will appear. Once all the data has been loaded, you can see the full database by running the next block of code.

The following blocks of code showcase examples of the functions described in the section above. The user can adjust the inputs to find specific information of interest.

## For Arianna re dashboard
So if you download the dash_testing.py file, then cd to whatever directory it's in via the command line (for me its "cd '/Users/anniewicker/Desktop/23-24/Fall_24/Automation' ", then type python dash_testing.py you should see a link like this http://127.0.0.1:8050/ somewhere in the output. If you paste that into your browser you should be able to see the dashboard.

