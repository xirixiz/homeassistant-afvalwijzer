import bs4
import requests
from datetime import datetime, timedelta, date

def scraper(url, trash=None):
    # today = datetime.today().strftime("%Y-%m-%d")
    # dateConvert = datetime.strptime(today, "%Y-%m-%d") + timedelta(days=1)
    # tomorrow = datetime.strftime(dateConvert, "%Y-%m-%d")

    if not trash:
        uniqueTrashTypes = []
        uniqueTrashNames = []
        trashDates = []
        trashSchedule = []
        devices = []

    page = requests.get(url)
    soup = bs4.BeautifulSoup(page.text, "html.parser")
    #soup = bs4.BeautifulSoup(page.text, "lxml")

    # Get trash date
    try:
        for element in soup.select('a[href*="#waste"] p[class]'):
            name = element.get_text()
            trashDates.append(name)
    except IndexError:
        return 'No matching trashname(s) found.'

    #trashDates = [i.split('\n', 1)[0] for i in uniqueTrashDates]
    uniqueTrashDates = [i.split('\n', 1) for i in trashDates]

    for item in uniqueTrashDates:
        uniqueTrashMeuk = {}
        uniqueTrashMeuk['key'] = item[1]
        uniqueTrashMeuk['value'] = item[0]
        trashSchedule.append(uniqueTrashMeuk)

    print (trashSchedule)


    # Get trash shortname
    try:
        for element in soup.select('a[href*="#waste"] p[class]'):
            devices.extend(element["class"])
        for element in devices:
            if element not in uniqueTrashTypes:
                uniqueTrashTypes.append(element)
    except IndexError:
        return 'No matching trashtype(s) found.'


    # Get trash longname
    try:
        for element in soup.select('span[class="afvaldescr"]'):
            name = element.get_text()
            if name not in uniqueTrashNames:
                uniqueTrashNames.append(name)
    except IndexError:
        return 'No matching trashname(s) found.'

    print (uniqueTrashTypes)
    print (uniqueTrashNames)

if __name__ == '__main__':
    trash = scraper('https://www.mijnafvalwijzer.nl/nl/xxxxxx/x')
    #print(trash)
