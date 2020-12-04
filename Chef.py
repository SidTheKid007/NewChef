from flask import Flask, render_template, request, session
from flask_session import Session
import json
import os
import pandas as pd
import plotly
import plotly.graph_objs as go
from pymongo import MongoClient
import requests
from scipy import stats


app = Flask(__name__)
SESSION_TYPE = 'filesystem'
app.config.from_object(__name__)
Session(app)


@app.route('/')
def loadHome():
    return render_template('index.html')


@app.route('/', methods=['POST'])
def addContact():
    try:
        name = (request.form['name'])
        email = (request.form['email'])
        client = MongoClient('mongodb+srv://siddhesvark:' + os.environ.get('MONGODB') + '@cluster0.mslk0.mongodb.net/emailList?retryWrites=true&w=majority')
        db = client.emailList
        emails = db.emails
        user = { "name": name, "email": email }
        emails.insert_one(user)
        emailList = "Thank you " + name + "!"
        return render_template('index.html', emailList = emailList)
    except Exception:
        emailList = "Thank you!"
        return render_template('index.html', emailList = emailList)        


@app.route('/plan')
def loadPlan():
    return render_template('plan.html')


@app.route('/build')
def loadBuild():
    return render_template('build.html')


@app.route('/grow')
def loadGrow():
    return render_template('grow.html')


@app.route('/blog')
def loadBlog():
    blogData = pd.read_csv('static/data/articles.csv')
    titles = blogData['Title'].values
    authors = blogData['Author'].values
    summaries = blogData['Summary'].values
    thumbnails = blogData['Thumbnail'].values
    links = blogData['Page'].values
    links = ['/blog/' + str(link) for link in links]
    linkCount = len(links)
    return render_template('blog.html', linkCount = linkCount, titles = titles, authors = authors, summaries = summaries, thumbnails = thumbnails, links = links)


@app.route('/competition')
def loadCompetition():
    return render_template('competition.html')


@app.route('/competition', methods=['POST'])
def analyzeLocation():
    try:
        address = (request.form['address'])
        yelpData = loadYelp(address)
        summaryInfo = categorySummary(yelpData)
        summary = summaryInfo[0]
        summaryTitle = getSummaryTitle('Count')
        summaryViz = categoryViz(summary, 'Count')
        others = summaryInfo[1]
        traffic = getTraffic(yelpData)
        trafficText = getTrafficText(traffic)
        topdf = findTops(yelpData)
        topLink = topdf['Link'].values
        topImg = topdf['Image'].values
        topName = topdf['Name'].values
        topType = topdf['Category'].values
        topRating = topdf['Rating'].values
        return render_template('competition-results.html', topLink = topLink, topImg = topImg, topName = topName, topType = topType, topRating = topRating, summaryViz = summaryViz, summaryTitle = summaryTitle, others = others, traffic = traffic, trafficText = trafficText)
    except Exception:
        errorMssg = "That address does not appear to be working right now."
        return render_template('competition.html', errorMssg = errorMssg)


@app.route('/diversity')
def loadDiversity():
    return render_template('diversity.html')


@app.route('/diversity', methods=['POST'])
def analyzeZip():
    try:
        zipcode = int(request.form['zip'])
        censusData = loadCensusData()
        homeData = loadHomeData()
        genderViz = makeGenderViz(censusData, zipcode)
        ethnicityViz = makeEthnicityViz(censusData, zipcode)
        housingViz = makeHousingViz(homeData, zipcode)
        avgAge = getAvgAge(censusData, zipcode)
        avgIncome = getAvgIncome(censusData, zipcode)
        avgHouse = getAvgHouse(censusData, zipcode)
        return render_template('diversity-results.html', genderViz = genderViz, ethnicityViz = ethnicityViz, housingViz = housingViz, avgAge = avgAge, avgIncome = avgIncome, avgHouse = avgHouse)
    except Exception:
        errorMssg = "That zip code does not appear to be working right now."
        return render_template('diversity.html', errorMssg = errorMssg)


@app.route('/blog/<page>')
def loadArticle(page):
    blogData = pd.read_csv('static/data/articles.csv')
    articleData = blogData[blogData['Page'] == int(page)]
    title = articleData['Title'].values[0]
    author = articleData['Author'].values[0]
    content = articleData['Body'].values[0]
    picture = articleData['Image'].values[0]
    return render_template('article.html', title = title, author = author, content = content, picture = picture)


@app.route('/summarychange', methods=['GET', 'POST'])
def changeSummary():
    selection = request.args['selection']
    summary = session['summary']
    distviz = categoryViz(summary, selection)
    return distviz


@app.route('/summarytitlechange', methods=['GET', 'POST'])
def changeSummaryTitle():
    selection = request.args['selection']
    disttitle = getSummaryTitle(selection)
    return disttitle


def loadYelp(address):
    url = 'https://api.yelp.com/v3/businesses/search?categories=restaurants&location=' + address + '&radius=4828&limit=50&sort_by=distance'
    # take out sort by distance?
    # maybe don't cap radius?
    # this looks at the 50 closest restaraunts or all restaraunts in a 3 mile radius (increase?) if less than 50
    # use offset in v2 to get full data scope
    headers = {
      'Authorization': 'Bearer ' + os.environ.get('YELP_APIKEY')
    }
    response = requests.request("GET", url, headers=headers)
    jsonresponse = json.loads(response.text)
    yelpdf = normalizeYelp(jsonresponse)
    #session['yelpdf'] = yelpdf
    return yelpdf


def normalizeYelp(jsonresponse):
    names = []
    images = []
    links = []
    reviews = []
    category = []
    rating = []
    distances = []
    #prices = []
    for business in jsonresponse['businesses']:
        names.append(business['name'])
        images.append(business['image_url'])
        links.append(business['url'])
        reviews.append(business['review_count'])
        category.append(business['categories'][0]['title'])
        rating.append(business['rating'])
        distances.append(business['distance'])
        # prices.append(business['price'])
    yelpdf = pd.DataFrame({'Name': names, 'Image': images, 'Link':links, 'Reviews':reviews, 'Category':category, 'Rating':rating, 'Distance':distances})
    return yelpdf


def categorySummary(yelpData):
    categorydf = yelpData[['Category', 'Reviews', 'Rating']]
    categorydf['Count'] = 1
    categorysumdf = categorydf.groupby(['Category']).sum().sort_values(by='Count', ascending=False)
    cleanedOthers = cleanOthers(categorysumdf)
    categorysumdf = cleanedOthers[0]
    others = cleanedOthers[1]
    others.sort()
    categories = categorysumdf.index.values
    categorysumdf = categorysumdf.reset_index(drop=True)
    categorysumdf.index = categories
    categorysumdf['Average Rating'] = categorysumdf['Rating'].values/categorysumdf['Count'].values
    categorysumdf['Average Review Count'] = categorysumdf['Reviews'].values/categorysumdf['Count'].values
    categorydf.loc[categorydf['Category'].isin(others), 'Category'] = 'Other'
    categorymindf = categorydf.groupby(['Category']).min()
    categorymaxdf = categorydf.groupby(['Category']).max()
    categorysumdf['Min Rating'] = categorymindf['Rating'].values
    categorysumdf['Max Rating'] = categorymaxdf['Rating'].values
    categorysumdf['Rating Range'] = categorysumdf['Min Rating'].astype(str) + ' - ' + categorysumdf['Max Rating'].astype(str)
    categorysumdf['Min Review Count'] = categorymindf['Reviews'].values
    categorysumdf['Max Review Count'] = categorymaxdf['Reviews'].values
    categorysumdf['Review Count Range'] = categorysumdf['Min Review Count'].astype(str) + ' - ' + categorysumdf['Max Review Count'].astype(str)
    categorysumdf = categorysumdf[categorysumdf['Count'] > 1][['Count', 'Average Rating', 'Rating Range', 'Average Review Count', 'Review Count Range']]
    summary = categorysumdf.round({'Average Rating': 2, 'Average Review Count': 0})
    session['summary'] = summary
    #summary = categorysumdf.to_html(classes='table-hover')
    others = 'Other is classified as categories with only 1 location. The categories that fall under Other are: ' + arrayToStr(others)
    return [summary, others]


def cleanOthers(categorysumdf):
    categorysumdf = categorysumdf.reset_index()
    others = categorysumdf[categorysumdf['Count'] == 1]['Category'].values
    categorysumdf.loc[categorysumdf['Count'] == 1, 'Category'] = 'Other'
    categorysumdf = categorysumdf.groupby(['Category']).sum()
    return [categorysumdf, others]


def arrayToStr(arr):
    arr[-1] = 'and ' +str(arr[-1])
    result = ''
    for k in arr:
        result = result + k + ', '
    result = result[:-2]
    return result


def categoryViz(summary, selection):
    categories = summary.index.values
    graphData = ''
    if (selection == 'Count'):
        heights = summary['Count'].values
        graphData = [go.Bar(x = categories, y = heights, hovertemplate ='%{y} restaraunts', name='')]
    elif (selection == 'Rating'):
        heights = summary['Average Rating'].values
        bonus = summary['Rating Range'].values
        graphData = [go.Bar(x = categories, y = heights, text = bonus, hovertemplate ='%{y}/5.0 <br>''Range: %{text}', name='')]
    else:
        heights = summary['Average Review Count'].values
        bonus = summary['Review Count Range'].values
        graphData = [go.Bar(x = categories, y = heights, text = bonus, hovertemplate ='%{y} reviews <br>''Range: %{text}', name='')]
    graphJSON = json.dumps(graphData, cls=plotly.utils.PlotlyJSONEncoder)
    return graphJSON


def getSummaryTitle(selection):
    title = ''
    if (selection == 'Count'):
        title = 'Total Count'
    elif (selection == 'Rating'):
        title = 'Average Ratings'
    else:
        title = 'Average Review Counts'
    return title


def getTraffic(yelpData):
    reviews = yelpData['Reviews'].values
    dists = yelpData['Distance'].values
    # use ml algo? (distance,rating,count of 5 closest places) -> count
    # limit it by dist? by head ( like yelpData.head(int(len(yelpData)/5) + 1))? or full data?
    weights = dists.max() + 1 - dists
    raw = 0
    for k in range(len(weights)):
        raw = raw + (weights[k] * reviews[k])
    raw = raw/weights.sum()
    traffic = round(stats.percentileofscore(yelpData['Reviews'].values, raw),2)
    return traffic


def getTrafficText(traffic):
    trafficText = ''
    if (traffic < 20):
        trafficText = 'Poor'
    elif (traffic < 40):
        trafficText = 'Subpar'
    elif (traffic < 60):
        trafficText = 'Average'
    elif (traffic < 80):
        trafficText = 'Great'
    else:
        trafficText = 'Excellent'
    return trafficText


def findTops(yelpData):
    topdf = 0
    if (len(yelpData[yelpData['Rating'] >= 4]) >= 10):
        topdf = yelpData[yelpData['Rating'] >= 4].sort_values(by='Reviews', ascending=False).head(3).sort_values(by='Rating', ascending=False)
    else:
        topdf = yelpData.sort_values(by='Rating', ascending=False).head(10).sort_values(by='Reviews', ascending=False).head(3).sort_values(by='Rating', ascending=False)
    return topdf


def loadCensusData():
    censusData = pd.read_csv('static/data/fullzip.csv')
    return censusData


def loadHomeData():
    homeData = pd.read_csv('static/data/houseprices.csv')
    return homeData


def makeGenderViz(censusData, zipcode):
    labels = ['Male', 'Female']
    values = censusData[censusData['Zip'] == zipcode].values[0][8:10]
    graphData = [go.Pie(labels = labels, values = values, name='')]
    graphJSON = json.dumps(graphData, cls=plotly.utils.PlotlyJSONEncoder)
    return graphJSON


def makeEthnicityViz(censusData, zipcode):
    categories = ['White', 'Black', 'Asian', 'Biracial', 'Other']
    zipPopulation = censusData[censusData['Zip'] == zipcode].values[0][2:7]
    zipPopulationPct = 100 * zipPopulation/sum(zipPopulation)
    zipPopulationPct = [round(num, 2) for num in zipPopulationPct]
    state = censusData[censusData['Zip'] == zipcode]['state_name'].values[0]
    statecategories = categories.copy()
    statecategories.append('state_name')
    stateData = censusData[censusData['state_name'] == state][statecategories].groupby(['state_name']).sum()
    statePopulation =  stateData.values[0]
    statePopulationPct = 100 * statePopulation/sum(statePopulation)
    statePopulationPct = [round(num, 2) for num in statePopulationPct]
    graphData = [go.Bar(x = categories, y = statePopulationPct, text = statePopulation, hovertemplate ='%{y}%<br>''%{text} people', name = state),
                go.Bar(x = categories, y = zipPopulationPct, text = zipPopulation, hovertemplate ='%{y}%<br>''%{text} people', name = str(zipcode))]
    graphJSON = json.dumps(graphData, cls=plotly.utils.PlotlyJSONEncoder)
    return graphJSON


def makeHousingViz(homeData, zipcode):
    zipData = homeData[homeData['Five-Digit ZIP Code'] == zipcode]
    year = zipData['Year'].values
    hpi = zipData['HPI'].values
    graphData = [go.Scatter(x = year, y = hpi, mode='lines+markers', fill='tozeroy', name='')]
    graphJSON = json.dumps(graphData, cls=plotly.utils.PlotlyJSONEncoder)
    return graphJSON


def getAvgAge(censusData, zipcode):
    avgAge = censusData[censusData['Zip'] == zipcode]['Age'].values[0]
    if pd.isna(avgAge):
        avgAge = 'N/A'
    else:
        avgAge = str(avgAge) + ' y/o'
    return avgAge


def getAvgIncome(censusData, zipcode):
    avgIncome = censusData[censusData['Zip'] == zipcode]['Household Income'].values[0]
    if pd.isna(avgIncome):
        avgIncome = 'N/A'
    else:
        avgIncome = '$' + str(round(avgIncome/1000, 1)) + ' K'
    return avgIncome


def getAvgHouse(censusData, zipcode):
    avgHouse = censusData[censusData['Zip'] == zipcode]['Home Price'].values[0]
    if pd.isna(avgHouse):
        avgHouse = 'N/A'
    elif (avgHouse > 1000000):
        avgHouse = '$' + str(round(avgHouse/1000000, 2)) + ' M'
    else:
        avgHouse = '$' + str(round(avgHouse/1000, 1)) + ' K'
    return avgHouse


