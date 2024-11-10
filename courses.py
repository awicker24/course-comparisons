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


