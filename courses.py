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
        # still need to convert time to seconds later
        
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

    def get_results(self, url, gender = 'women', drop_dnf=True, drop_dns=True):
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

    def get_runner_id(self, name, eligibility, school):
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
    
    def get_race_id(self, race, date): #, distance):  #NOOOOTTTTT FINNNISHHHEDDDDD   -   distance ??
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

    
    def load_results(self, url, gender = 'women', drop_dnf=True, drop_dns=True):
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
        ------------------------------------------------- STATISTICS --------------------------------------------------------------
        '''

    def compare_two_courses(self, RaceIDOne, RaceIDTwo):  # need to change id to race name

        sql = '''
        WITH CommonRunnersTable AS
        (
            WITH CommonRunnersList AS
            (
                    SELECT runner_id, race_id, COUNT(*) AS NumRaces
                    FROM tRaceResult
                    GROUP BY runner_id
                    HAVING NumRaces > 1 
            )
        SELECT runner_id FROM CommonRunnersList
        ),
        
        CourseOne AS
        (
        SELECT Avg(time) AS AvgCourseOne
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
        SELECT AvgCourseOne, AvgCourseTwo
        FROM CourseOne
        JOIN CourseTwo
        )
        
        SELECT AvgCourseTwo - AvgCourseOne AS Difference, AvgCourseTwo / AvgCourseOne AS Ratio
        FROM BothCourses
        
        ;'''
                    
        results = self.run_query(sql, {'RaceIDOne':RaceIDOne, 'RaceIDTwo':RaceIDTwo}) 
        
        return results


    def see_loaded_races(self):

        results = self.run_query('''SELECT * FROM tRace''')
        
        return results
    
    def course_lookup(self, partial_race_name):
        '''
        Find courses with partial_race_name as a keyword and return all results from that race
        '''
        sql = '''
        SELECT * FROM tRace
        JOIN tRaceResult USING (race_id)
        WHERE race LIKE '%' || :partial_name || '%' 
        ;'''
        results = self.run_query(sql, {'partial_name': partial_race_name})
        return results
    
    def find_races_in_common(self, runner_id_1, runner_id_2):
        '''
        Find all races that two runners have in common
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
    
    def predict_times(self, target_course_id):
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


    def conversions(self, primary_race_id):
        '''
        connects courses together to compare times
        User specifies one race they want to be the point of comparison. All other courses are given a ratio based on how much 
        faster or slower they are from the specified course, as well as a number of seconds faster or slower they are. Results
        are outputed in a dataframe. Ratios will be more accurate than time differences due to varying speeds of runners
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

        # find all the courses that share at least 15 runners with the primary
        secondary_list = []
        non_secondary_list = []
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

        # iterate thru all the teriary races
        for item in non_secondary_list:
            tertiary_race_id = item

            # select all the courses except the current tertiary one
            courses = self.run_query('''
                SELECT race_id
                FROM tRace
                WHERE race_id NOT LIKE :this_race
                ;''',
                {"this_race":tertiary_race_id})['race_id'].tolist()
            courses_to_compare = list(set(courses) - set(non_secondary_list)) #remove all other tertiary courses

            tertiary_table = pd.DataFrame(columns = ['Difference', 'Ratio', 'NumCompared'])

            # for each tertiary race, go through all the non-tertiary races to find the ratios and differences
            for race in courses_to_compare:
                results = self.compare_two_courses(race, tertiary_race_id) # run the comparison function on each course
                tertiary_table = pd.concat([tertiary_table, results], ignore_index=True)

            # merge data for tertiary table with data from all courses in order to do calculations
            tertiary_table['race_id'] = courses_to_compare
            tertiary_table = pd.merge(
                tertiary_table,
                coursesdf[['race_id','ratio_conversion','time_conversion']],
                on = 'race_id',
                how = 'inner')
        
            this_ratio = 0
            this_diff = 0
            total_comparisons = tertiary_table['NumCompared'].sum() # find the total number of runners compared - used to weight each race average
    
            for row in tertiary_table.itertuples(index=False): # iterate thru tuples to calculate
                this_ratio += row.Ratio*row.ratio_conversion*row.NumCompared/total_comparisons # new ratio is primary:secondary * secondary:teriary * weight
                this_diff += (row.Difference + row.time_conversion)*row.NumCompared/total_comparisons 
                # new time diff is ((secondary - primary) + (teriary - secondary)) * weight based on number of runners compared

            coursesdf.loc[coursesdf['race_id'] == tertiary_race_id, 'ratio_conversion'] = this_ratio # add calculated ratio to dataframe
            coursesdf.loc[coursesdf['race_id'] == tertiary_race_id, 'time_conversion'] = this_diff # add calculated time difference to dataframe

        return coursesdf
    
    
    def predict_team_results(self, school, course_id):
        predictions_df = self.predict_times(course_id)
        
        team_results = predictions_df[predictions_df['school'] == school]
        
        team_results = team_results[['runner_id', 'name', 'predicted_time', 'formatted_time']]
        
        return team_results
        
