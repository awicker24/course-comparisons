from bs4 import BeautifulSoup, NavigableString
import requests
import pandas as pd

def get_results(url, gender = 'women', drop_dnf=True, drop_dns=True):
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
    soup = BeautifulSoup(page.text, 'html')
    
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
        
    return df
