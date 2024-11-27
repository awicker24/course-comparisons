import pandas as pd
import sqlite3
import courses
from importlib import reload
import dash
from dash import Dash, dcc, html, Input, Output, State, callback, dash_table
import plotly.express as px

#initialize the app
app = Dash(__name__)

app.title = 'Course Comparisons'

db = courses.CoursesDB('courses.db', create = False) 

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

app.layout = html.Div([
    html.H1("Race Data"),
    
    #full data table
    html.Div([
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
    ]),
    
    #course comparisons
    html.Div([
        html.H2("Compare Two Courses"),
        
        #dropdown menus
        html.Label("Select First Course:"),
        dcc.Dropdown(
            id='course-one-dropdown',
            options=[{'label':row['race'], 'value':row['race_id']} for _, row in race_data.iterrows()],
            placeholder="Select the first course",
        ),
        
        html.Label("Select Second Course:"),
        dcc.Dropdown(
            id='course-two-dropdown',
            options=[{'label':row['race'], 'value':row['race_id']} for _, row in race_data.iterrows()],
            placeholder="Select the second course",
        ),
        
        html.Button("Compare Courses", id='compare-button', n_clicks=0),
        
        html.Div(id='comparison-result', style={'marginTop':'20px'}),
    ])
])

@app.callback(
    Output('comparison-result', 'children',),
    Input('compare-button', 'n_clicks'),
    State('course-one-dropdown', 'value'),
    State('course-two-dropdown', 'value')
)

def compare_course(n_clicks, course_one, course_two):
    if not course_one or not course_two:
        return "Please select two courses to compare."
    
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
     
if __name__ == '__main__':
    app.run_server(debug=True)
    
    
##make font better
##more functionality obviously