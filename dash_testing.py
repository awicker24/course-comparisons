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

db = courses.CoursesDB('courses.db', create = False)

'''----------------Simple Query Functions----------------'''

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
                            html.H2("Predict Runner Times on a Course"),
                            html.P("Please select a course to predict."),
                            dcc.Dropdown(
                                id='course-dropdown',
                                options=[{'label':row['race'], 'value':row['race_id']} for _, row in race_data.iterrows()
                                    ],
                                placeholder="Select race",
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
    
    if difference is None or ratio is None:
        return 'No data available for comparison.'

    return html.Div([
        html.P(f"Difference in Average Times: {difference:.2f} seconds"),
        html.P(f"Ratio of Average Times: {ratio:.2f}")
    ])

#callback for predicting times
@app.callback(
    Output('prediction-result', 'children'),
    Input('predict-button', 'n_clicks'),
    State('course-dropdown', 'value')
)

def predict_times_callback(n_clicks, target_course_id):    
    if not n_clicks or target_course_id is None:
        return "Click 'Predict Times' after selecting a course."
    try:
        predictions_df = db.predict_times(target_course_id)
        return html.Div([
            html.H3(""),
            html.P("Filter for a specific runner or team by typing underneath the column name."),
            dash_table.DataTable(
                data=predictions_df.to_dict('records'),
                columns=[
                    {'name': 'Runner ID', 'id': 'runner_id'},
                    {'name': 'Name', 'id': 'name'},
                    {'name': 'School', 'id': 'school'},
                    {'name': 'Predicted Time', 'id': 'formatted_time'}
                ],
                filter_action="native",
                sort_action="native",
            )
        ])
    except Exception as e:
        print(f"Error: {e}")
        return f"Error: {str(e)}"
                      
if __name__ == '__main__':
    app.run_server(debug=True)
