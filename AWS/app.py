"""
Author: David Jorge

This is the app script for launching the dashboard for the LTE-M Edge Sensor Project.
"""

import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import pullS3

# Get external stylesheet
external_stylesheets = [
    {
        "href": "https://fonts.googleapis.com/css2?"
                "family=Lato:wght@400;700&display=swap",
        "rel": "stylesheet",
    },
]

# Initialize dashboard
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
app.title = "LTE-M Edge Sensor Dashboard"

# Initialize AWS API library
aws = pullS3.pullS3()
aws.pull()


def getCounts():
    """
    Helper function for getting the parcel condition total counts from the AWS API script.

    :return: List - Good Condition Count, Bad Condition Count.
    """
    return [aws.count["Parcel"], aws.count["Damaged Parcel"]]


# Define the dashboard HTML layout
app.layout = html.Div(
    children=[
        html.Div(
            children=[
                html.P(children="📦", className="header-emoji"),
                html.P(children="📡", className="header-emoji"),
                html.H1(
                    children="LTE-M Sensor Analytics", className="header-title"
                ),
                html.P(
                    children="Analyze the output of the LTE-M sensor"
                             " stored in AWS",
                    className="header-description",
                ),
            ],
            className="header",
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.H1(
                            id="live-update-header", children="Latest Parcel", className="header-description2"
                        ),
                        html.Img(
                            id="live-update-img",
                            src=app.get_asset_url("{}.png".format(aws.mostRecent[0])),
                            className="image",
                        ),
                        html.Div(
                            [
                                html.Span(
                                    children="Condition: ",
                                ),
                                html.Span(
                                    id="cond",
                                    children="Good" if aws.mostRecent[1] == "Parcel" else "Bad",
                                    className="label-good" if aws.mostRecent[1] == "Parcel" else "label-bad",
                                ),
                            ],
                            id="parcel-label",
                            className="label",
                        ),
                        html.H1(
                            id="live-update-metadata", children="Parcel Info", className="header-description3"
                        ),
                        html.Img(
                            id="live-update-barcode",
                            src=app.get_asset_url("{}-b.png".format(aws.mostRecent[0])),
                            className="image barcode",
                        ),
                        html.H1(
                            id="live-update-metadata2", children="Parcel Info", className="header-description4"
                        ),
                        dcc.Interval(
                            id='interval-component',
                            interval=60 * 1000,  # in milliseconds
                            n_intervals=0
                        ),
                    ],
                    className="card",
                    id="test"
                ),
                html.Div(
                    [
                        dcc.Graph(
                            id="count-chart",
                            figure={
                                "data": [
                                    {"x": ["Parcel", "Damaged Parcel"], "y": getCounts(), "type": "bar"},
                                ],
                                "layout": {
                                    "title": {
                                        "text": "Condition",
                                    },
                                    "xaxis": {"tickmode": "linear", "tick0": 0, "dtick": 1},
                                    "colorway": ["#17B897"],
                                },
                            }
                        )
                    ],
                    className="card"
                ),
                html.Div(
                    [
                        dcc.Graph(
                            id="hourly-chart",
                            figure={
                                "data": [
                                    {"x": aws.df["Date"], "y": aws.df["Count"], "type": "bar", },
                                ],
                                "layout": {
                                    "title": {
                                        "text": "Hourly Deliveries",
                                    },
                                    "xaxis": {"fixedrange": True},
                                    "yaxis": {
                                        "fixedrange": True,
                                    },
                                    "colorway": ["#E12D39"],
                                },
                            }
                        )
                    ],
                    className="card"
                ),
            ],
            className="wrapper",
        ),
    ]
)


# Define callback function to implement live update of data on the dashboard.
@app.callback(Output(component_id='live-update-img', component_property='src'),
              Output(component_id='live-update-barcode', component_property='src'),
              Output(component_id="count-chart", component_property="figure"),
              Output(component_id="hourly-chart", component_property="figure"),
              Output(component_id="cond", component_property="children"),
              Output(component_id="cond", component_property="className"),
              Input(component_id='interval-component', component_property='n_intervals'))
def update_metrics(n_intervals):
    # Get up to date data
    aws.pull()

    # Update parcel condition total count bar graph
    updatedFigBar = {
        "data": [
            {"x": ["Good Condition", "Bad Condition"], "y": getCounts(), "type": "bar"},
        ],
        "layout": {
            "title": {
                "text": "Condition",
            },
            "xaxis": {"tickmode": "linear", "tick0": 0, "dtick": 1},
            "colorway": ["#17B897"],
        },
    }

    # Update hourly delivery count bar graph
    updatedFigHourly = {
        "data": [
            {"x": aws.df["Date"], "y": aws.df["Count"], "type": "bar", },
        ],
        "layout": {
            "title": {
                "text": "Hourly Deliveries",
            },
            "xaxis": {"fixedrange": True},
            "yaxis": {
                "fixedrange": True,
            },
            "colorway": ["#E12D39"],
        },
    }

    # Update condition text and style
    condition = "Good" if aws.mostRecent[1] == "Parcel" else "Bad"
    newClassName = "label-good" if aws.mostRecent[1] == "Parcel" else "label-bad"

    return app.get_asset_url("{}.png".format(aws.mostRecent[0])), app.get_asset_url(
        "{}-b.png".format(aws.mostRecent[0])), updatedFigBar, updatedFigHourly, condition, newClassName


if __name__ == "__main__":
    app.run_server(debug=False)
