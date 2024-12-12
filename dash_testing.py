import pandas as pd
import sqlite3
import courses
from courses import CoursesDB
from importlib import reload
import dash
from dash import Dash, dcc, html, Input, Output, State, callback, dash_table
from urllib.parse import urlparse
import plotly.express as px
import os

#initialize the app
app = Dash(__name__)
    
app.title = 'Course Comparisons'

db_file = 'courses.db'

if os.path.exists(db_file):
    db = courses.CoursesDB('courses.db', create = False)
else:
    print("!!!!No database found. Download the courses.db file from the Github repository!!!!")

#getting full table with all data: 
query = '''
SELECT * FROM tRunner
JOIN tRaceResult USING (runner_id)
JOIN tRace USING (race_id)
;'''
initial_data = db.run_query(query).to_dict("records")

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

#Dash app layout                       
app.layout = html.Div(
    [
        dcc.Tabs(
            [
                dcc.Tab(
                    label="Import Data",
                    children=[
                        html.H1("Race Results"),
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
                        html.Button("Scrape and Load Results", id="scrape-button"),
                        html.Div(id="output"),
                        html.Div(
                            [
                                dash_table.DataTable(
                                    id='race-table',
                                    columns=[{"name":col, "id":col} for col in db.run_query(query).columns],
                                    data=initial_data,
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
                    label="Compare Courses",
                    children=[
                        html.H2("Compare Two Courses"),
                        html.P("Select two courses to compare."),
                        #dropdown menus
                        dcc.Dropdown(
                            id='course-one-dropdown',
                            options=[{'label':row['race'], 'value':row['race_id']} for _, row in race_data.iterrows()],
                            placeholder="Select the first course",
                        ),
                        dcc.Dropdown(
                            id='course-two-dropdown',
                            options=[{'label':row['race'], 'value':row['race_id']} for _, row in race_data.iterrows()],
                            placeholder="Select the second course",
                        ),
                        html.Button("Compare Courses", id='compare-button', n_clicks=0),
                        html.Div(id='comparison-result', style={'marginTop':'20px'}),
                        
                        html.H2("Compare All Courses"),
                        html.P("Select one course as a point of comparison. Courses must have a minimum of 15 runners in common to be comparable."),
                        dcc.Dropdown(
                            id="full-course-dropdown",
                            options=[{'label':row['race'], 'value':row['race_id']} for _, row in race_data.iterrows()],
                            placeholder="Select a course",
                        ),
                        html.Button("Compare", id="full-compare-button"),
                        html.P("To estimate a runner's time in a different race, multiply their time for the primary race by the ratio. Their time combines how many seconds you'd have to add or subtract to the average person's time in the primary race to estimate their time in the secondary race. If no ratios or times besides 0 and 1 are shown in the table, there were not enough runners in common between the races."),
                        html.Div(id="output-2"),
                    ]
                ),
                dcc.Tab(
                    label="Predict Times",
                    children=[
                        html.H2("Predict Runner Times on a Course"),
                        html.P("Select a course to predict."),
                        dcc.Dropdown(
                            id='course-dropdown',
                            options=[{'label':row['race'], 'value':row['race_id']} for _, row in race_data.iterrows()],
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
    Output("race-table", "data"),
    [Input("scrape-button", "n_clicks")],
    [State("gender-dropdown", "value"),
     State("url-input", "value")]
)
def load_or_scrape_data(n_clicks, gender, url):
    if n_clicks is None:
        initial_data = db.run_query(query)
        return initial_data.to_dict("records")
    
    if not url:
        return []
    
    try:
        db.load_results(url, gender)
        updated_data = db.run_query(query)
        return updated_data.to_dict("records")
    except Exception as e:
        return []

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
    results = db.run_query(sql, {'RaceIDOne':course_one, 'RaceIDTwo':course_two})
    
    if results.empty:
        return ""
    difference = results['Difference'].iloc[0]
    ratio = results['Ratio'].iloc[0]
    
    if difference is None or ratio is None:
        return 'No data available for comparison.'

    return html.Div([
        html.P(f"Difference in Average Times: {difference:.2f} seconds"),
        html.P(f"Ratio of Average Times: {ratio:.2f}")
    ])

#callback for full course comparison (conversions function)
@app.callback(
    Output("output-2", "children"),
    Input("full-compare-button", "n_clicks"),
    State("full-course-dropdown", "value")
)

def conversions_callback(n_clicks, primary_race_id, min_comparisons=15):
    if not n_clicks or primary_race_id is None:
        return ""
    
    try: 
        courses_df = db.conversions(primary_race_id)
        return html.Div([
            html.H3(""),
            dash_table.DataTable(
                data=courses_df.to_dict("records"),
                columns=[
                    {"name":"Race ID", "id": "race_id"},
                    {"name":"Race", "id":"race"},
                    {"name":"Date", "id":"date"},
                    {"name":"Ratio", "id":"ratio_conversion"},
                    {"name":"Time", "id":"time_conversion"}
                ],
                filter_action="native",
                sort_action="native",
            )
        ])
    except Exception as e:
        print(f"Error: {e}")
        return f"Error: {str(e)}"
        
                    
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
