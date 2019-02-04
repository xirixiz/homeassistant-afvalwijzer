import itertools
from datetime import date, datetime, timedelta

import requests

import bs4
import re
import locale

def scraper(url, trash=None):
    if not trash:
        trashDump = []
        json_data = []

    page = requests.get(url, allow_redirects=True)
    soup = bs4.BeautifulSoup(page.text, "html.parser")

    today = datetime.today().strftime("%d-%m-%Y")
    today_date = datetime.strptime(today, "%d-%m-%Y")
    dateConvert = datetime.strptime(today, "%d-%m-%Y") + timedelta(days=1)
    tomorrow = datetime.strftime(dateConvert, "%d-%m-%Y")
    tomorrow_date = datetime.strptime(tomorrow, "%d-%m-%Y")

    # Get current year
    for item in soup.select('[class="ophaaldagen"]'):
        year_id = item["id"]
    year = re.sub('jaar-','',year_id)

    #print("test", soup.find('div', attrs={'class':'ophaaldagen'}).text)

    # Get trash date
    try:
        for data in soup.select('a[href*="#waste"] p[class]'):
            element = data["class"]
            for item in element:
                x = item
            name = data.get_text()
            trashDump.append(name)
            trashDump.append(x)
    except IndexError:
        return 'No matching trashname(s) found.'

    uniqueTrashDates = [i.split('\n', 1) for i in trashDump]
    uniqueTrashDates = list(itertools.chain.from_iterable(uniqueTrashDates))
    uniqueTrashDates = [uniqueTrashDates[i:i+3]for i in range(0,len(uniqueTrashDates),3)]

    def _get_month_number(month):
        if month == 'januari':
            return '01'
        elif month == 'februari':
            return '02'
        elif month == 'maart':
            return '03'
        elif month == 'april':
            return '04'
        elif month == 'mei':
            return '05'
        elif month == 'juni':
            return '06'
        elif month == 'juli':
            return '07'
        elif month == 'augustus':
            return '08'
        elif month == 'september':
            return '09'
        elif month == 'oktober':
            return '10'
        elif month == 'november':
            return '11'
        elif month == 'december':
            return '12'
        else:
            return None

    trashDump = []
    trashSchedule = []
    json_data = []
    try:
        for item in uniqueTrashDates:
            split_date = item[0].split(' ')
            day = split_date[1]
            month_name = split_date[2]
            month = _get_month_number(month_name)
            trashDump = {}
            trashDump['key'] = item[2]
            trashDump['description'] = item[1]
            trashDump['value'] = (day + '-' + month + '-' + year)
            json_data.append(trashDump)
    except IndexError:
        return 'No matching trashname(s) found.'

    defaultTrashNames = ['today', 'tomorrow', 'next']
    uniqueTrashNames = []
    uniqueTrashNames.extend(defaultTrashNames)
    trashSchedule = []

    for item in json_data:
        key = item['key']
        description = item['description']
        value = item['value']
        value_date = datetime.strptime(item['value'], "%d-%m-%Y")
        if value_date >= today_date:
            if key not in uniqueTrashNames:
                trash = {}
                trash['key'] = key
                trash['description'] = description
                trash['value'] = value
                uniqueTrashNames.append(key)
                trashSchedule.append(trash)

    # Collect data
    today_out = [x for x in trashSchedule if datetime.strptime(x['value'], "%d-%m-%Y") == today_date]
    tomorrow_out = [x for x in trashSchedule if datetime.strptime(x['value'], "%d-%m-%Y") == tomorrow_date]
    next_out = [x for x in trashSchedule if datetime.strptime(x['value'], "%d-%m-%Y") > today_date]

    # Append Today data
    trashToday = {}
    multiTrashToday = []
    if len(today_out) == 0:
        trashToday['key'] = 'today'
        trashToday['description'] = 'Trash Today'
        trashToday['value'] = 'None'
        trashSchedule.append(trashToday)
    else:
        for x in today_out:
            trashToday['key'] = 'today'
            trashToday['description'] = 'Trash Today'
            multiTrashToday.append(x['key'])
        trashSchedule.append(trashToday)
        trashToday['value'] = ', '.join(multiTrashToday)

    #Append Tomorrow data
    trashTomorrow = {}
    multiTrashTomorrow = []
    if len(tomorrow_out) == 0:
        trashTomorrow['key'] = 'tomorrow'
        trashTomorrow['description'] = 'Trash Tomorrow'
        trashTomorrow['value'] = 'None'
        trashSchedule.append(trashTomorrow)
    else:
        for x in tomorrow_out:
            trashTomorrow['key'] = 'tomorrow'
            trashTomorrow['description'] = 'Trash Tomorrow'
            multiTrashTomorrow.append(x['key'])
        trashSchedule.append(trashTomorrow)
        trashTomorrow['value'] = ', '.join(multiTrashTomorrow)

    # Append next pickup in days
    trashNext = {}

    def d(s):
        [year, month, day] = map(int, s.split('-'))
        return date(day, month, year)
    def days(start, end):
        return (d(end) - d(start)).days

    if len(next_out) == 0:
       trashNext['key'] = 'next'
       trashNext['value'] = 'None'
       trashSchedule.append(trashNext)
    else:
        if len(trashNext) == 0:
            trashNext['key'] = 'next'
            trashNext['description'] = 'Next Pickup In Days'
            trashNext['value'] = (days(today, next_out[0]['value']))
            trashSchedule.append(trashNext)

    print(trashToday)
    print(trashTomorrow)
    print(trashNext)
    print(trashSchedule)





    # # Get trash shortname
    # try:
    #     for item in trashSchedule:
    #         element = item.get('key')
    #         if element not in uniqueTrashShortNames:
    #             uniqueTrashShortNames.append(element)
    # except IndexError:
    #     return 'No matching trashname(s) found.'

    # #print (uniqueTrashShortNames)

    # # Get trash longname
    # try:
    #     for item in trashSchedule:
    #         element = item.get('description')
    #         if element not in uniqueTrashLongNames:
    #            uniqueTrashLongNames.append(element)
    # except IndexError:
    #     return 'No matching trashname(s) found.'

    # #print (uniqueTrashLongNames)



    # ALTERNATIVES

    # # Get trash shortname
    # try:
    #     for element in soup.select('a[href*="#waste"] p[class]'):
    #         devices.extend(element["class"])
    #     for element in devices:
    #         if element not in uniqueTrashShortNames:
    #             uniqueTrashShortNames.append(element)
    # except IndexError:
    #     return 'No matching trashtype(s) found.'

    # #print (uniqueTrashShortNames)


    # # Get trash longname
    # try:
    #     for element in soup.select('span[class="afvaldescr"]'):
    #         name = element.get_text()
    #         if name not in uniqueTrashLongNames:
    #             uniqueTrashLongNames.append(name)
    # except IndexError:
    #     return 'No matching trashname(s) found.'

    # #print (uniqueTrashLongNames)

if __name__ == '__main__':
    trash = scraper('https://www.mijnafvalwijzer.nl/nl/5142CA/337/A')
