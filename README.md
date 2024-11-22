# Cross Country Course Comparisons
## Description
This repository contains files that can be used for the scraping and analyzing of results data from cross country races. Ultimately, the files will enable a user to run virtual meets, standardize courses of varying difficulty, and track runner improvement throughout the season.

## Getting Started:
The `tffrsdatascraping.py` is the standalone web scraping function. It takes a URL from the Track and Field Results Reporting System (TFRRS) and defaults to scraping women's results, but the 'gender' argument can be changed to gender=men for men's results. The function automatically drops racers' times who did not start (DNS) or did not finish (DNF) the race. 

`courses.py` creates a database of all user-inputted TFRRS data. It incorporates the webscraping script to load the data into the database, and contains numerous functions for running queries on the database. `see_loaded_races` allows the user to check which races have been loaded into the database. The `compare_two_courses` function takes two unique race IDs as inputs, and returns the difference in average time, time ratio, and the number of runners in two races. This function only compares races with **at least one** runner in common. `course_lookup` allows a user to input a partial course name to find all of the races run at one course. Because one course can host multiple races, this function is useful for users who want to compare times on the same course at different points in a season. `find_races_in_common` takes two unique runner IDs as inputs and outputs all of the races that those two runners have run. 

`CourseFunctions.ipynb` provides a sample use of the database in its full functionality. This file contains example outputs of all the functions being run on a database with loaded races. 

## Using the Program

Begin by downloading both the `courses.py` file and the `CourseFunctions.ipynb` notebook in the same folder. The `courses.py` file contains the functions which allow the user to create and query the database, but all commands to access this code will be run from the `CourseFunctions.ipynb` notebook. After loading the necessary libraries, initialize the database by running the third block of code with the 'create' argument set to True. Then, run the next block to create the tables. You are now ready to begin loading data into the database.

All data loaded into this database will come from individual race pages on the TFRRS website. Links to these pages can be found here: https://www.tfrrs.org/.

Begin entering data by running the block of code containing the `db.load_results` function, entering the URLs of any races you would like to load into the database.

