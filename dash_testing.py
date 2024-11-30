import pandas as pd
import sqlite3
import courses
from courses import CoursesDB
from importlib import reload
import dash
from dash import Dash, dcc, html, Input, Output, State, callback, dash_table
from urllib.parse import urlparse
import plotly.express as px

#initialize the app
app = Dash(__name__)
    
app.title = 'Course Comparisons'

db = courses.CoursesDB('courses.db', create = False) #change to false if not running for the first time
#db.drop_all_tables(are_you_sure = True)
#db.build_tables()

def load_results(url, gender = 'women', drop_dnf=True, drop_dns=True):
        frame = db.get_results(url, gender, drop_dnf, drop_dns)
        #db.connect()
        # cols = [ ... ]
        # new_sales_file.columns = cols
        
        for i, row in enumerate(frame.to_dict(orient='records')):
            # get or create runner_id for this name/eligibility/school combo (use get_runner_id)
            runner_id = db.get_runner_id(row['NAME'], row['YEAR'], row['TEAM'])
            # get or create race_id for this race/date combo
            race_id = db.get_race_id(row['COURSE'], row['DATE']) # add distance
            # fill in tables
            row['runner_id'] = runner_id
            row['race_id'] = race_id
            try:
                sql = '''
                INSERT INTO tRaceResult (runner_id, race_id, time, raw_time, place) VALUES (:runner_id, :race_id, :CONVERTED, :TIME, :PL)
                ;'''
                db.curs.execute(sql, row) 
            except Exception as e:
                print(e)
                print('\nrow: ', i)
                print('\n', row)
                db.conn.rollback() # Undo everything since the last commit 
                db.close()
                raise e
        db.conn.commit()
        db.close()
        return None

#getting full table with all data: 
query = '''
SELECT * FROM tRunner
JOIN tRaceResult USING (runner_id)
JOIN tRace USING (race_id)
;'''
full_data = db.run_query(query)

#getting unique race names from dropdown options
race_names_query = '''
SELECT DISTINCT race_id, race
FROM tRace
;'''
race_data = db.run_query(race_names_query)

#unique runners and teams for dropdown options
runners_query = '''
SELECT DISTINCT runner_id, name
FROM tRunner
;'''
runners_data = db.run_query(runners_query)

teams_query = '''
SELECT DISTINCT school
FROM tRunner
;'''
teams_data = db.run_query(teams_query)

#combine runners and teams in one dropdown options list
runner_team_options = [{'label':row['name'], 'value':f"runner_{row['runner_id']}"} for _, row in runners_data.iterrows()] + \
                      [{'label':row['school'], 'value':f"team_{row['school']}"} for _, row in teams_data.iterrows()] 

#Dash app layout                       
app.layout = html.Div(
    [
        dcc.Tabs(
            [
                dcc.Tab(
                    label="Import Data",
                    children=[
                        html.H1("Race Data"),
                        
                        dcc.Dropdown(
                            id='gender-dropdown',
                            options=[
                                {'label':'Women', 'value':'women'},
                                {'label':'Men', 'value':'men'}
                            ],
                            value='women',
                        ),
                        dcc.Input(
                            id='url-input',
                            type='text',
                            placeholder='Enter race URL...',
                            style={'width':'60%'}
                        ),
                        html.Button('Scrape and Load Results', id='scrape-button'),
                        html.Div(id='output'),
                        
                        html.Div(
                            [
                                html.H2("Complete Race Data"),
                                dash_table.DataTable(
                                    id='race-table',
                                    columns=[{"name":col, "id":col} for col in full_data.columns],
                                    data=full_data.to_dict("records"),
                                    style_table={"height": "500px", "overflowY": "auto"},
                                    filter_action="native",
                                    sort_action="native",
                                    page_action="none"
                                )
                            ]
                        ),
                    ]
                ),
                dcc.Tab(
                    label="Compare Two Courses",
                    children=[
                        html.H2("Compare Two Courses"),
                        html.P("Please select two courses to compare."),
                        html.Label("Select First Course:"),
                        #dropdown menus
                        dcc.Dropdown(
                            id='course-one-dropdown',
                            options=[{'label':row['race'], 'value':row['race_id']} for _, row in race_data.iterrows()
                                    ],
                            placeholder="Select the first course",
                        ),
                        html.Label("Select Second Course:"),
                        dcc.Dropdown(
                            id='course-two-dropdown',
                            options=[{'label':row['race'], 'value':row['race_id']} for _, row in race_data.iterrows()
                                    ],
                            placeholder="Select the second course",
                        ),
                        html.Button("Compare Courses", id='compare-button', n_clicks=0),
                        html.Div(id='comparison-result', style={'marginTop':'20px'}),
                    ]
                ),
                    dcc.Tab(
                        label="Predict Times",
                        children=[
                            html.H2("Predict Runner or Team Times on a Course"),
                            html.P("Please select a runner/team and a course to predict."),
                            html.Div(id="instruction-message", style={'color': 'red', 'marginBottom':'10px'}),
                            html.Label("Select Runner or Team:"),
                            dcc.Dropdown(
                                id='runner-team-dropdown',
                                options=runner_team_options, 
                                placeholder="Select a runner or team",
                            ),
                            html.Label("Select Course:"),
                            dcc.Dropdown(
                                id='predict-course-dropdown',
                                options=[{'label':row['race'], 'value':row['race_id']} for _, row in race_data.iterrows()
                                        ],
                                placeholder="Select a course",
                            ),
                            html.Button("Predict Times", id='predict-button', n_clicks=0),
                            html.Div(id='prediction-result', style={'marginTop':'20px'}),
                        ]
                    ),
            ]
        )
    ]
)              
#callback for TFRRS URL
@app.callback(
    Output('output', 'children'),
    [Input('scrape-button', 'n_clicks'),
     Input('gender-dropdown', 'value'), 
     Input('url-input', 'value')]
)
def scrape_and_load_results(n_clicks, gender, url):
    if n_clicks is None:
        return ""
    if not url:
        return "Please provide a valid race URL."
    
    try:
        db.load_results(url, gender)
        return f"Results successfully loaded for {gender} from the race at {url}"
    except Exception as e:
        return f"Error: {str(e)}"

#callback for course comparisons
@app.callback(
    Output('comparison-result', 'children',),
    Input('compare-button', 'n_clicks'),
    State('course-one-dropdown', 'value'),
    State('course-two-dropdown', 'value')
)

def compare_course(n_clicks, course_one, course_two):   
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
        SELECT Avg(time) as AvgCourseOne
        FROM tRaceResult
        WHERE runner_id IN CommonRunnersTable AND race_id = :RaceIDOne
    ),
    
    CourseTwo AS
    (
        SELECT Avg(time) as AvgCourseTwo
        FROM tRaceResult
        WHERE runner_id IN CommonRunnersTable AND race_id = :RaceIDTwo
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
    #i changed this so that it asks for race name not id               
    results = db.run_query(sql, {'RaceIDOne':course_one, 'RaceIDTwo':course_two})
    
    if results.empty:
        return "No data available for comparison."
    difference = results['Difference'].iloc[0]
    ratio = results['Ratio'].iloc[0]
    
    
    
    return html.Div([
        html.P(f"Difference in Average Times: {difference:.2f} seconds"),
        html.P(f"Ratio of Average Times: {ratio:.2f}")
    ])

#callback for predicting times
@app.callback(
    [Output('instruction-message', 'children'),
     Output('prediction-result', 'children')],
    [Input('runner-team-dropdown', 'value'),
    Input('predict-course-dropdown', 'value')]
)

def predict_times_callback(runner_team, course_id):    
    #ensure both dropdowns have selected values
    if not runner_team or not course:
        return "Please select both a runner/team and a course to make a prediction.", None
    #determine if input is a runner or team
    if runner_team.startswith("runner_"):
        runner_id = runner_team.split("_")[1]
        predictions_df = db.predict_times(course_id)
        runner_prediction = predictions.df[predictions_df['runner_id'] == int(runner_id)]
        if runner_prediction.empty:
            return "No prediction available for this runner."
        formatted_time = runner_prediction['formatted_time'].iloc[0]
        return f"Prediction time: {formatted_time}"
    elif runner_team.startswith('team_'):
        team_name = runner_team.split("_")[1]
        predictions_df = predictions_df.merge(
            db.run_query('SELECT runner_id, school FROM tRunner WHERE school = ?', [team_name]), 
            on = 'runner_id'
        )
        if team_predictions.empty:
            return "No prediction available for this team."
        team_avg_time = team_predictions['predicted_time'].mean()
        minutes = int(team_avg_time // 60)
        seconds = int(team_avg_time % 60)
        return f"Prediction average time: {minutes}.{seconds:02d}"
            
    
     
if __name__ == '__main__':
    app.run_server(debug=True)
