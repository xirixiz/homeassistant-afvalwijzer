import bs4
import requests
import itertools
from datetime import datetime, timedelta, date

def scraper(url, trash=None):
    if not trash:
        trashDump = []
        trashSchedule = []
        uniqueTrashShortNames = []
        uniqueTrashLongNames = []

    page = requests.get(url)
    soup = bs4.BeautifulSoup(page.text, "html.parser")

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

    try:
        for item in uniqueTrashDates:
            trashDump = {}
            trashDump['key'] = item[2]
            trashDump['description'] = item[1]
            trashDump['value'] = item[0]
            trashSchedule.append(trashDump)
    except IndexError:
        return 'No matching trashname(s) found.'

    print (trashSchedule)

    # Get trash shortname
    try:
        for item in trashSchedule:
            element = item.get('key')
            if element not in uniqueTrashShortNames:
                uniqueTrashShortNames.append(element)
    except IndexError:
        return 'No matching trashname(s) found.'

    print (uniqueTrashShortNames)

    # Get trash longname
    try:
        for item in trashSchedule:
            element = item.get('description')
            if element not in uniqueTrashLongNames:
               uniqueTrashLongNames.append(element)
    except IndexError:
        return 'No matching trashname(s) found.'

    print (uniqueTrashLongNames)



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
    trash = scraper('https://www.mijnafvalwijzer.nl/nl/xxxx/x')
    #print(trash)
