import json, sys
import mysql.connector
from selenium import webdriver
from bs4 import BeautifulSoup

with open('semesters.json') as fd:
    semesters = json.load(fd)

search_results = {}
cnx = mysql.connector.connect(user='root', password='TESTPASSWORD',
                              host='localhost',
                              database='test_schema')

cur = cnx.cursor()
add_courses_query = ("INSERT INTO courses(course_code, name, faculty, department) VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE "
                     "course_code=course_code")


add_semester_listings_query = ("INSERT INTO course_offerings(course, credits, semester) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE "
                               "course=course")

driver = webdriver.Firefox()
driver.implicitly_wait(5)
driver.get('https://w2prod.sis.yorku.ca/Apps/WebObjects/cdm')
table_tag = driver.find_element_by_xpath("//td[@valign='top']/table")
table_tag.find_elements_by_tag_name('a')[1].click() # go to search page
for semester in semesters['targets']:
    try:
        session_search_link = driver.find_element_by_xpath("//select[@name='sessionPopUp']/option[@value='{}']".format(
            semester['sessionPopUp']))
        if not session_search_link.get_attribute('selected'):
            session_search_link.click()

        semester_search_link = driver.find_element_by_xpath("//select[@name='periodPopUp']/option[@value='{}']".format(
            semester['semesterPopUp']))
        if not semester_search_link.get_attribute('selected'):
            semester_search_link.click()
    except Exception:
        continue

    driver.find_element_by_xpath("//input[@type='submit']").click()
    search_results[semester['semesterName']] = driver.page_source

    # To get around caching issues where clicking back returns a document expired page,
    # we just need to click back one more time (the loop is for safe measure)
    retries = 0
    while True:
        try:
            if retries < 10:
                driver.back()
                break
            else:
                driver.close()
                sys.exit(14)
        except Exception:
            retries += 1
driver.close()

#
#
courses_offered = {}
courses_by_semester = dict()
courses_by_semester.setdefault('S1', [])
courses_by_semester.setdefault('S2', [])
courses_by_semester.setdefault('SU', [])
courses_by_semester.setdefault('Y', [])
courses_by_semester.setdefault('W', [])
courses_by_semester.setdefault('F', [])

for semester, page in search_results.items():
    bs = BeautifulSoup(page, "html.parser")
    courses = bs.find('td', {'valign': 'TOP'}).find('tbody').findAll('tr')[2].findAll('table')[3].findAll('tr')[1:]
    # grab names + codes, list of tuples (e.g. (ADMS 1000, Introduction to business))
    courses = list(map(lambda x: (x[0].text, x[1].text), map(lambda x: x.findAll('td')[:2], courses)))
    for course in courses:
        name = ' '.join(course[1].rsplit()) # Some names have formatting issues (leading/trailing whitespace), this will get rid of that
        course_code_and_credits = course[0].rsplit()
        course_credits = float(course_code_and_credits[2])
        course_code = ' '.join(course_code_and_credits[:2])
        faculty = course_code.split('/')[0]
        dept = course_code.split('/')[1].rsplit()[0]
        courses_offered[course_code] = (course_code, name, faculty, dept)
        courses_by_semester[semester].append((course_code, course_credits))
        print((course_code, semester, course_credits, name, faculty, dept))


def safe_guard():
    safe_guard_input = input("Ready to add courses to database. Continue? (Y/N)")
    if safe_guard_input.lower() == "n":
        cnx.commit()
        cur.close()
        cnx.close()
        sys.exit(0)
    elif safe_guard_input.lower() == "y":
        for course_offered in courses_offered.values():
            cur.execute(add_courses_query, (course_offered[0], course_offered[1], course_offered[2], course_offered[3]))
        for semester, courses in courses_by_semester.items():
            if len(courses) >= 1:
                for course in courses:
                    cur.execute(add_semester_listings_query, (course[0], course[1], semester))

        cnx.commit()
        cur.close()
        cnx.close()
    else:
        print("Please select a valid option")
        safe_guard()


safe_guard()
