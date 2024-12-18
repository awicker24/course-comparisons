import sqlite3
import pandas as pd
import os
import numpy as np
from glob import glob
import shutil
from bs4 import BeautifulSoup
import requests

class CoursesDB:
    def __init__(self, path_db, create=False):
        self.db_exists(path_db, create)
        return

    
    def connect(self):
        self.conn = sqlite3.connect(self.path_db)
        self.curs = self.conn.cursor()
        self.curs.execute("PRAGMA foreign_keys = ON;")
        return

    
    def close(self):
        self.conn.close()
        return

    
    def run_query(self, sql, params=None, manage_conn = True):
        self.connect()
        results = pd.read_sql(sql, self.conn, params = params)
        if manage_conn: self.close()
        return results

       
        '''
        ------------------------------------------------- DATABASES & TABLES --------------------------------------------------------------
        '''

    
    def db_exists(self, path_db, create):
        '''
        Check if the database file exists,
        if it does not, then either alert the user
        or create it if 'create' is True
        '''
        if os.path.exists(path_db):
            self.path_db = path_db
        else:
            if create == True:
                conn = sqlite3.connect(path_db)
                conn.close()
                self.path_db = path_db
                print('Database created at', path_db)
            else:
                raise FileNotFoundError(path_db + ' does not exist.')
        return

    
    def drop_all_tables(self, are_you_sure=False):
        '''
        Drop all tables from the database
        '''
        self.connect()
        
        try:
            self.curs.execute("DROP TABLE IF EXISTS tRaceResult;")
            self.curs.execute("DROP TABLE IF EXISTS tRace;")
            self.curs.execute("DROP TABLE IF EXISTS tRunner;")
            self.curs.execute("DROP TABLE IF EXISTS tTeam;")
        except Exception as e:
            self.close()
            raise e
        self.close()
        return


    def build_tables(self):
        '''
        Build all tables in the database,
        assuming they do not exist
        '''
        self.connect()
        
        sql = """
        CREATE TABLE tRunner (
            runner_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            eligibility TEXT NOT NULL,
            school TEXT NOT NULL 
        )
        ;"""
        self.curs.execute(sql) 
    

        sql = """
        CREATE TABLE tRaceResult (
            runner_id INTEGER REFERENCES tRunner(runner_id),
            race_id INTEGER REFERENCES tRace(race_id),  
            raw_time TEXT NOT NULL, 
            time FLOAT NOT NULL,
            place INTEGER NOT NULL,
            PRIMARY KEY(runner_id, race_id)   
        )
        ;"""
        self.curs.execute(sql)
        
        sql = """
        CREATE TABLE tRace (
            race_id INTEGER PRIMARY KEY,
            race TEXT NOT NULL,
            date TEXT NOT NULL
            -- distance TEXT NOT NULL
        )
        ;"""
        self.curs.execute(sql)
        
        self.close()
        return


        '''
        ------------------------------------------------- WEB SCRAPING --------------------------------------------------------------
        '''

    def get_results(self, url:str, gender = 'women', drop_dnf=True, drop_dns=True):
        '''
        A function that takes a race URL from TFRRS and returns scraped results
        from that race. By default it returns women's results. Pass 'men' to 
        the gender argument to get men's results. Runners who did not finish
        (DNF) or did not start (DNS) are removed from scraped results. To     
        keep them in the results, change drop_dnf and drop_dns to False.
        '''
        
        #get course name from url:
        course_name_part = url.split('/')[-1] #getting the course name from after the slash (ie Panorama_Farms_Invitational)
        course_name = course_name_part.replace('_', ' ').strip() #getting rid of underscores (ie Panorama Farms Invitational)
        
        #initializing webscraper in html format:
        page = requests.get(url)
        soup = BeautifulSoup(page.text, 'lxml') #, originally html
        
        #getting the date from the results:
        date_div = soup.find('div', class_ = 'panel-heading-normal-text inline-block')
        date = date_div.text.strip() if date_div else "Unknown Date"
        
        #finding all of the results that exist on the page - men's and women's team, men's and women's individual:
        tables = soup.find_all('table')
        titles = soup.find_all('div', class_ = 'custom-table-title custom-table-title-xc')
                               
        #going through the titles of each table to skip team results and scrape men's or women's results depending on user input:
        for i, title_div in enumerate(titles):
            title_text = title_div.find('h3', class_ = 'font-weight-500').text.strip()
            
            if "Team" in title_text:
                continue
                
            if (gender == "women" and "Women" not in title_text) or \
               (gender == "men" and "Men" not in title_text):
                continue
        
            #getting the columns for the scraped data based on columns that are in the results:
            table = tables[i]
            world_titles = table.find_all('th')
            world_table_titles = [title.text.strip() for title in world_titles]
            
        #initializing the data frame
        df = pd.DataFrame(columns = world_table_titles + ['COURSE', 'DATE'])
            
        #each individual result in each table starts with 'tr' - finding all of those and stripping them:
        column_data = table.find_all('tr')
        for row in column_data[1:]:
            if hasattr(row, 'find_all'):
                row_data = row.find_all('td')
                individual_row_data = [data.text.strip() for data in row_data]
                
                #removing DNF/DNS (did not finish or did not start):
                if drop_dnf and "DNF" in individual_row_data: #remove DNFs (can change to FALSE if want them in there)
                    continue
                if drop_dns and "DNS" in individual_row_data: #same for DNS
                    continue
                
                individual_row_data.append(course_name)
                individual_row_data.append(date)
                
                #making the length of the data frame the length of the row data from the results:
                length = len(df)
                df.loc[length] = individual_row_data
            
        #removing any extra columns (like splits for each 1k or any extra info) from the results so all the dataframes are uniform:
        desired_columns = ['PL', 'NAME', 'YEAR', 'TEAM', 'Avg. Mile', 'TIME', 'SCORE', 'COURSE', 'DATE']
        extra_columns = [col for col in df.columns if col not in desired_columns]
        if extra_columns:
            df = df.drop(columns=extra_columns)
        
        df['PL'] = df['PL'].astype(int)
        df = self.time_to_seconds(df)
    
        return df

    def time_to_seconds(self, frame):
        frame['CONVERTED'] = frame['TIME'].apply(lambda x: int(x[0:2])*60 + float(x[3:7]) if len(x) == 7 else x)
        return frame
        

        '''
        ------------------------------------------------- DYNAMIC DATA --------------------------------------------------------------
        '''

    def get_runner_id(self, name:str, eligibility:str, school:str):
        '''
        check if runner_id exists for this combo
        add runner_id if not
        '''
        
        sql_check = "SELECT runner_id FROM tRunner WHERE name LIKE ? AND eligibility LIKE ? AND school LIKE ?;"
        x = pd.read_sql(sql_check, self.conn, params = (name, eligibility, school))
        
        # if not, create it (run an INSERT)
        if len(x) == 0:
            sqlite3.register_adapter(np.int64, lambda val: int(val))
            sql_insert = "INSERT INTO tRunner (name, eligibility, school) VALUES (?, ?, ?);" 
            self.curs.execute(sql_insert, (name, eligibility, school))
        x = pd.read_sql(sql_check, self.conn, params = (name, eligibility, school))
        # return it   
        runner_id = x.iloc[0,0]
        return runner_id
    
    def get_race_id(self, race:str, date): 
        '''
        check if race_id exists for this combo
        create race_id and add race to tRace if not
        !ARIS
        '''
        sql_check = "SELECT race_id FROM tRace WHERE race LIKE ? AND date LIKE ?;" # AND distance LIKE ?;"
        x = pd.read_sql(sql_check, self.conn, params = (race, date)) #, distance))
        
        # if not, create it (run an INSERT)
        if len(x) == 0:
            sqlite3.register_adapter(np.int64, lambda val: int(val))
            sql_insert = "INSERT INTO tRace (race, date) VALUES (?, ?);"
            self.curs.execute(sql_insert, (race, date)) #, distance))
        x = pd.read_sql(sql_check, self.conn, params = (race, date)) #, distance))
        # return it   
        race_id = x.iloc[0,0]
        return race_id

    
    def load_results(self, url:str, gender = 'women', drop_dnf=True, drop_dns=True):
        frame = self.get_results(url, gender, drop_dnf, drop_dns)
        self.connect()
        # cols = [ ... ]
        # new_sales_file.columns = cols
        
        for i, row in enumerate(frame.to_dict(orient='records')):
            # get or create runner_id for this name/eligibility/school combo (use get_runner_id)
            runner_id = self.get_runner_id(row['NAME'], row['YEAR'], row['TEAM'])
            # get or create race_id for this race/date combo
            race_id = self.get_race_id(row['COURSE'], row['DATE']) # add distance
            # fill in tables
            row['runner_id'] = runner_id
            row['race_id'] = race_id
            try:
                sql = '''
                INSERT INTO tRaceResult (runner_id, race_id, time, raw_time, place) VALUES (:runner_id, :race_id, :CONVERTED, :TIME, :PL)
                ;'''
                self.curs.execute(sql, row) 
            except Exception as e:
                print(e)
                print('\nrow: ', i)
                print('\n', row)
                self.conn.rollback() # Undo everything since the last commit 
                self.close()
                raise e
        self.conn.commit()
        self.close()
        return None


        '''
        ------------------------------------------------- BASIC QUERIES --------------------------------------------------------------
        '''
    def see_loaded_races(self):
        '''
        Outputs a list of all races that have been loaded into the database
        '''

        results = self.run_query('''SELECT * FROM tRace''')
        
        return results

    
    def course_lookup(self, partial_race_name:str):
        '''
        Finds courses with partial_race_name as a keyword and return all races with that fragment in their name
        '''
        sql = '''
        SELECT * FROM tRace
        WHERE race LIKE '%' || :partial_name || '%' 
        ;'''
        results = self.run_query(sql, {'partial_name': partial_race_name})
        return results


    def runner_lookup(self, partial_runner_name:str):
        '''
        Finds runners with partial_runner_name as a keyword and return all runners with that fragment in their name
        '''
        sql = '''
        SELECT * FROM tRunner
        WHERE name LIKE '%' || :partial_name || '%' 
        ;'''
        results = self.run_query(sql, {'partial_name': partial_runner_name})
        return results

    
    def find_races_in_common(self, runner_id_1:int, runner_id_2:int):
        '''
        Finds all races that two people have run together
        '''
        sql = '''
        SELECT * FROM tRace
        WHERE race_id IN (
            SELECT race_id
            FROM tRaceResult
            WHERE runner_id = :runner_id_1
            INTERSECT
            SELECT race_id
            FROM tRaceResult
            WHERE runner_id = :runner_id_2
            )
            ;'''
        results = self.run_query(sql, {'runner_id_1': runner_id_1, 'runner_id_2': runner_id_2})
        return results
        '''
        ------------------------------------------------- CONVERSIONS AND STATISTICS -------------------------------------------------
        '''
    
    def compare_two_courses(self, RaceIDOne:int, RaceIDTwo:int):  
        '''
        This function compares two courses specified by their race_id's.
        It will output the difference in seconds in average race times (difference), the ratio of average race times (ratio), and
        the number of runners in common between the two courses (NumCompared).
        The first course is used as a comparison point. 'difference' is the number of seconds faster or slower that the second course
        averages compared to the first course; a negative value for 'difference' means the second course was faster.
        'ratio' is the number that race times from the first course would need to be multiplied by in order to standardize them to the second 
        course; the average time from the first course multiplied by 'ratio' should yield the average time from the second course.
        This function only compares times in runners who competed in both meets. The number of runners in common is shown as NumCompared.
        '''

        
        sql = '''
        WITH CommonRunnersTable AS
        (
            WITH CommonRunnersList AS
            (
                    SELECT runner_id, race_id, COUNT(*) AS NumRaces
                    FROM tRaceResult
                    WHERE race_id LIKE :RaceIDOne OR race_id LIKE :RaceIDTwo 
                    GROUP BY runner_id
                    HAVING NumRaces > 1 
            )
        SELECT runner_id FROM CommonRunnersList
        ),
        
        CourseOne AS
        (
        SELECT Avg(time) AS AvgCourseOne, COUNT(*) AS NumCompared
        FROM tRaceResult
        WHERE runner_id IN CommonRunnersTable AND race_id LIKE :RaceIDOne
        ),
        
        CourseTwo AS
        (
        SELECT Avg(time) AS AvgCourseTwo
        FROM tRaceResult
        WHERE runner_id IN CommonRunnersTable AND race_id LIKE :RaceIDTwo
        ),
        
        BothCourses AS
        (
        SELECT AvgCourseOne, AvgCourseTwo, NumCompared
        FROM CourseOne
        JOIN CourseTwo
        )
        
        SELECT AvgCourseTwo - AvgCourseOne AS Difference, AvgCourseTwo / AvgCourseOne AS Ratio, NumCompared
        FROM BothCourses

        ;'''
                    
        results = self.run_query(sql, {'RaceIDOne':RaceIDOne, 'RaceIDTwo':RaceIDTwo}) 
        
        return results


    
    def predict_times(self, target_course_id:int):
        '''
        Predicts times for runners on a specific course
        '''
       
        #gets all the runners who results from multiple races
        sql = '''
        SELECT tRaceResult.runner_id, tRunner.name, tRunner.school, tRaceResult.race_id, tRaceResult.time, tRaceResult.place
        FROM tRaceResult
        JOIN tRunner
        ON tRaceResult.runner_id = tRunner.runner_id
        WHERE tRaceResult.runner_id IN (
            SELECT runner_id
            FROM tRaceResult
            GROUP BY runner_id
            HAVING COUNT(race_id) > 1
        )
        ;'''
   
        shared_runners_df = self.run_query(sql)
       
        #groups data by course and gets average time for each course
        avg_times_per_course = shared_runners_df.groupby('race_id')['time'].mean().reset_index()
        avg_times_per_course.columns = ['race_id', 'avg_time'] #renaming columns
       
        #filter avg_time_per_course for race_id matching target_course_id in input
        target_avg_time = avg_times_per_course[avg_times_per_course['race_id'] == target_course_id]['avg_time'].values[0]
       
        #creating a new column difficulty_ratio that takes course average times and divides in by the target course average time
        #high difficulty ratio (>1) harder course, <1 easier course
        avg_times_per_course['difficulty_ratio'] = avg_times_per_course['avg_time']/target_avg_time
   
        #merge difficulty ratios with dataframe obtained by sql query
        shared_runners_ratios = pd.merge(
        shared_runners_df,
        avg_times_per_course[['race_id', 'difficulty_ratio']],
        on = 'race_id',
        how = 'left'
        )
   
        #loops through dataframe for all unique runner ids and creates a predicted time by multiplying the course's difficulty ratio by the course time, then takes the average of the difficulty ratio-adjusted course times
        predicted_times = []
        for runner_id in shared_runners_ratios['runner_id'].unique():
            runner_data = shared_runners_ratios[shared_runners_ratios['runner_id'] == runner_id]
       
            predicted_time = (runner_data['time'] * runner_data['difficulty_ratio']).mean()
        
            runner_name = runner_data['name'].iloc[0]
            
            runner_school = runner_data['school'].iloc[0]
           
            
            #convert to minutes:seconds format
            minutes = int(predicted_time // 60)
            seconds = int(predicted_time % 60)
            formatted_time = f"{minutes}:{seconds:02d}"
       
            predicted_times.append({'runner_id': runner_id, 
                                    'name': runner_name, 
                                    'school': runner_school, 
                                    'predicted_time': predicted_time, 
                                    'formatted_time': formatted_time})
 
        predictions_df = pd.DataFrame(predicted_times)
   
        return predictions_df


    def conversions(self, primary_race_id:int, min_comparisons = 15):
        '''
        connects courses together to compare times
        User specifies one race they want to be the point of comparison. All other courses are given a ratio based on how much 
        faster or slower they are from the specified course, as well as a number of seconds faster or slower they are. Results
        are outputed in a dataframe. Ratios will be more accurate than time differences due to varying speeds of runners
        min_comparisons can be set as the number of runners that a race must have in common in order to be compared. It will
        default to 15 if not set.
        A positive value for time_conversion and a value of ratio_conversion greater than 1 both indicate that a course was slower
        than the primary course
        '''

        coursesdf = self.see_loaded_races() # look up all the courses loaded into the database
        num_races = len(coursesdf) # find number of races loaded
        if primary_race_id > num_races: # error prevention
            print('Race ID out of range')
            return None
        convert_ratio = [None] * num_races # create a list of the right length
        coursesdf['ratio_conversion'] = convert_ratio # use this list to add a new column to the df for conversions
        coursesdf.loc[coursesdf['race_id'] == primary_race_id, 'ratio_conversion'] = 1 # set the primary course ratio as 1
        convert_time = [None] * num_races
        coursesdf['time_conversion'] = convert_time
        coursesdf.loc[coursesdf['race_id'] == primary_race_id, 'time_conversion'] = 0 # set the primary course time difference as 0
        
        
        # select all the courses except the one listed as primary
        course_list = self.run_query('''
            SELECT race_id
            FROM tRace
            WHERE race_id NOT LIKE :primary_race
            ;''',
            {"primary_race":primary_race_id})['race_id'].tolist()

        # find all the courses that share at least 'min_comparisons' runners with the primary
        secondary_list = []
        non_secondary_list = []
        quaternary_list = []
        unusable_courses = []
        for id in course_list:
            common = self.run_query('''
                WITH CommonRunnersList AS
                (
                        SELECT runner_id, race_id, COUNT(*) AS NumRaces
                        FROM tRaceResult
                        WHERE race_id LIKE :RaceIDOne OR race_id LIKE :RaceIDTwo 
                        GROUP BY runner_id
                        HAVING NumRaces > 1 
                )
                
                SELECT COUNT(runner_id) AS CommonRunners
                FROM CommonRunnersList
                ;''',
                {'RaceIDOne':primary_race_id, 'RaceIDTwo':id}).iat[0,0] # the .iat[0,0] part grabs the value from the df
            if common > 14:
                secondary_list.append(id)
            else: 
                non_secondary_list.append(id)

        for item in secondary_list:
            secondary_race_id = item
            # run the comparison function for each race with enough runners in common with primary race
            results = self.compare_two_courses(primary_race_id, secondary_race_id) 
            
            time_diff = results.loc[0,'Difference'] # from the results, grab the average difference in seconds
            coursesdf.loc[coursesdf['race_id'] == secondary_race_id, 'time_conversion'] = time_diff
            
            ratio = results.loc[0,'Ratio'] # from the results, grab the average ratio difference
            coursesdf.loc[coursesdf['race_id'] == secondary_race_id, 'ratio_conversion'] = ratio

        # select all the courses that aren't tertiary
        all_courses = coursesdf['race_id'].tolist() # select all courses
        courses_to_compare = list(set(all_courses) - set(non_secondary_list)) # remove all tertiary courses
  
        # iterate thru all the teriary races
        for item in non_secondary_list:
            tertiary_race_id = item

            tertiary_table = pd.DataFrame(columns = ['Difference', 'Ratio', 'NumCompared'])

            used_race_ids = []
            # for each tertiary race, go through all the non-tertiary races to find the ratios and differences
            for race in courses_to_compare:
                results = self.compare_two_courses(race, tertiary_race_id) # run the comparison function on each course
                common_runners = results.loc[0,'NumCompared']
                if common_runners > 0:
                    tertiary_table = pd.concat([tertiary_table, results], ignore_index=True) # if there are runners in common, add row to table
                    used_race_ids.append(race) # store id to add to table

            # merge data for tertiary table with data from all courses in order to do calculations
            tertiary_table['race_id'] = used_race_ids
            tertiary_table2 = pd.merge(
                tertiary_table,
                coursesdf[['race_id','ratio_conversion','time_conversion']],
                on = 'race_id',
                how = 'inner')
        
            this_ratio = 0
            this_diff = 0
            total_comparisons = tertiary_table2['NumCompared'].sum() # find the total number of runners compared - used to weight each race average
            if total_comparisons > min_comparisons:    
                for row in tertiary_table2.itertuples(index=False): # iterate thru tuples to calculate
                    this_ratio += row.Ratio*row.ratio_conversion*row.NumCompared/total_comparisons # new ratio is primary:secondary * secondary:teriary * weight
                    this_diff += (row.Difference + row.time_conversion)*row.NumCompared/total_comparisons 
                    # new time diff is ((secondary - primary) + (teriary - secondary)) * weight based on number of runners compared
    
                coursesdf.loc[coursesdf['race_id'] == tertiary_race_id, 'ratio_conversion'] = this_ratio # add calculated ratio to dataframe
                coursesdf.loc[coursesdf['race_id'] == tertiary_race_id, 'time_conversion'] = this_diff # add calculated time difference to dataframe
            else:
                quaternary_list.append(item)

        # select all courses that aren't quaternary
        all_courses = coursesdf['race_id'].tolist() # select all courses
        courses_to_compare = list(set(all_courses) - set(quaternary_list)) # remove all quaternary courses

        # iterate thru all quaternary courses
        for item in quaternary_list:
            quaternary_race_id = item

            quaternary_table = pd.DataFrame(columns = ['Difference', 'Ratio', 'NumCompared'])

            used_race_ids = []
            # for each quaternary race, go through all the non-quaternary races to find the ratios and differences
            for race in courses_to_compare:
                results = self.compare_two_courses(race, quaternary_race_id) # run the comparison function on each course
                common_runners = results.loc[0,'NumCompared']
                if common_runners > 0:
                    quaternary_table = pd.concat([quaternary_table, results], ignore_index=True) # if there are runners in common, add row to table
                    used_race_ids.append(race) # store id to add to table

            # merge data for quaternary table with data from all courses in order to do calculations
            quaternary_table['race_id'] = used_race_ids
            quaternary_table2 = pd.merge(
                quaternary_table,
                coursesdf[['race_id','ratio_conversion','time_conversion']],
                on = 'race_id',
                how = 'inner')
        
            this_ratio = 0
            this_diff = 0
            total_comparisons = quaternary_table2['NumCompared'].sum() # find the total number of runners compared - used to weight each race average
            if total_comparisons > min_comparisons:    
                for row in quaternary_table2.itertuples(index=False): # iterate thru tuples to calculate
                    this_ratio += row.Ratio*row.ratio_conversion*row.NumCompared/total_comparisons 
                    # new ratio is primary:secondary * secondary:teriary * tertiary:quaternary * weight
                    this_diff += (row.Difference + row.time_conversion)*row.NumCompared/total_comparisons 
                    # new time diff is ((secondary - primary) + (teriary - secondary) + (quaternary - tertiary_) * weight based on number of runners compared
    
                coursesdf.loc[coursesdf['race_id'] == quaternary_race_id, 'ratio_conversion'] = this_ratio # add calculated ratio to dataframe
                coursesdf.loc[coursesdf['race_id'] == quaternary_race_id, 'time_conversion'] = this_diff # add calculated time difference to dataframe
            else:
                unusable_courses.append(item)
                print('Note: not enough information to compare race ' + str(item) + '. Only ' + str(total_comparisons) + ' runners in common.')

        return coursesdf 
    
    
    def predict_team_results(self, school:str, course_id:int):
        predictions_df = self.predict_times(course_id)
        
        team_results = predictions_df[predictions_df['school'] == school]
        
        team_results = team_results[['runner_id', 'name', 'predicted_time', 'formatted_time']]
        
        return team_results
        

    def select_schools(self, schools:list, primary=1):
        '''
        Inputs a list of schools and a race, and a primary course ID which defaults to 1, outputs the results from each 
        race of all runners from these two schools after having standardized these results with the conversions function
        '''
        schools_tuple = tuple(schools)
        # grab all runners in the database from the selected schools
        # the .join part adds the number of question marks needed to the query based on how many schools are selected
        query = 'SELECT runner_id, school FROM tRunner WHERE school IN (' + str(', '.join(['?']*len(schools))) + ');' 
        racers = self.run_query(query, params = schools_tuple)
        results = self.run_query('''SELECT runner_id, race_id, time FROM tRaceResult ;''')

        # get all the race results from the database for runners in the specified schools
        runner_results = pd.merge(
        racers,
        results,
        on = 'runner_id',
        how = 'left'
        )

        #run the conversion function
        race_conversions = self.conversions(primary)
        race_conversions.drop(['race', 'date','time_conversion'], axis=1, inplace=True) # remove extra columns
        race_conversions = race_conversions.dropna() # remove courses that couldn't be converted

        # convert all the times
        converted_results = pd.merge(
            runner_results,
            race_conversions,
            on = 'race_id',
            how = 'inner'
            )
        converted_results['time_conversion'] = converted_results.time / converted_results.ratio_conversion # standardize
        converted_results = converted_results[['runner_id','race_id','time_conversion']]
        
        return converted_results


    def virtual_race(self, schools:list, primary=1):
        ''' 
        Inputs a list of schools to run a virutal meet against and a course to set as primary (defaults to 1), 
        outputs the expected results from a meet with those teams
        '''
        #get the list of runners and their converted times at each race from the select_schools function
        converted_results = self.select_schools(schools, primary)

        # pivot the table so all the runners (runner_id's) are the rows and each race is a column
        results_table = converted_results.pivot(index='runner_id', columns='race_id', values='time_conversion')
        # add a column averaging all of the converted times
        results_table['average_time'] = results_table.sum(axis=1) / results_table.count(axis=1)
        # only select the runner_ids and average times
        average_times = results_table[['average_time']]
        average_times.reset_index(inplace=True) # turn runner_id back from index to normal column
        # now grab all the runner names and schools from tRunner
        runners = self.run_query('''SELECT runner_id, name, school FROM tRunner;''')
        race = pd.merge(  # create match average times to a runner's name and school
            average_times,
            runners,
            on = 'runner_id',
            how = 'left'
            )
        race = race.sort_values(by='average_time') # order the dataframe
        race.reset_index(inplace=True) # reset the index in correct order
        race['estimated_time'] = race['average_time'].apply(lambda x: str(int(x // 60)) + ':' + str(float(x % 60))[0:4]) #change time to MM:SS.D
        race.drop(['index','average_time'], axis=1, inplace=True)
        
        return race
