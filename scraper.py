import json, sys, os
import mysql.connector
import datetime
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from bs4 import BeautifulSoup
from traceback import format_exc
from pyvirtualdisplay import Display

print('Starting scraper.')
os.chdir(sys.path[0])
use_headless = False

try:
    display = Display(visible=0, size=(800, 600))
    display.start()
except Exception as e:
    use_headless = True

with open('semesters.json') as fd:
    semesters = json.load(fd)

fd = open('log.txt', 'a+')
fd.write("--------------------------{}--------------------------------\r\n\r\n\r\n".format(datetime.datetime.now().strftime(
    "%d-%m-%Y %H:%M")))
fd.flush()


try:
    search_results = {}

    ADD_COURSE_QUERY = (
        "INSERT INTO courses(course_code, name, faculty, department, description, credits) VALUES "
        "(%s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE "
        "course_code=course_code")

    ADD_COURSE_OFFERING_QUERY = (
        "INSERT INTO course_offerings(term, course, director, section, course_credits) VALUES "
        "(%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE "
        "course_offering_id=LAST_INSERT_ID(course_offering_id)")

    ADD_COURSE_TIME_QUERY = (
        "INSERT INTO course_times(day, location, start_time, duration, type, instructor, CAT, time_string, course_offering) VALUES "
        "(%s, %s, %s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE "
        "id=id")

    unique_courses = {}
    course_offerings = {}
    redundant_check = {}
    DAY_CONVERSION = {'M': 'Monday', 'T': 'Tuesday', 'W': 'Wednesday', 'R': 'Thursday', 'F': 'Friday', 'S': 'Saturday',
                      'U': 'Sunday', 'SU': 'Saturday and Sunday', 'MWF': 'Monday, Wednesday and Friday',
                      'TR': 'Tuesday and Thursday', 'N/A': 'N/A'}
    SEMESTER_SET = set(map(lambda x: str(x['semesterName']), semesters['targets']))

    if use_headless:
        options = Options()
        options.add_argument('-headless')
        driver = webdriver.Firefox(options=options)
    else:
        driver = webdriver.Firefox(executable_path=r'/home/ubuntu/geckodriver')

    driver.implicitly_wait(5)


    def go_to_search_page():
        driver.get("https://w2prod.sis.yorku.ca/Apps/WebObjects/cdm")
        table_tag = driver.find_element_by_xpath("//td[@valign='top']/table")
        table_tag.find_elements_by_tag_name('a')[1].click()  # go to search page


    # To get around caching issues where clicking back returns a document expired page,
    # we just need to click back one more time (the loop is for safe measure)
    def go_back():
        for i in range(11):
            try:
                driver.back()
                break
            except Exception:
                if i == 10:
                    driver.close()
                    sys.exit(14)
                else:
                    continue


    for semester in semesters['targets']:
        go_to_search_page()
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

        bs = BeautifulSoup(driver.page_source, "html.parser")
        courses = bs.find('td', {'valign': 'TOP'}).find('tbody').findAll('tr')[2].findAll('table')[3].findAll('tr')[1:]
        # grab names + codes, list of tuples (e.g. (ADMS 1000, Introduction to business))
        for course in courses:
            # grab name, course code, schedule link
            meta = course.findAll('td')[:3]

            # Grab unique course data
            name = meta[1].text.strip()
            course_code_and_credits = meta[0].text.rsplit()
            course_credits = float(course_code_and_credits[2])
            course_code = ' '.join(course_code_and_credits[:2])
            faculty = course_code.split('/')[0]
            dept = course_code.split('/')[1].rsplit()[0]
            # print((course_code, name, course_credits))
            # Check if we already got this course's schedule
            if redundant_check.get(course_code + str(course_credits) + name, None) is not None:
                continue

            # grab schedule
            schedule_link = meta[2].find('a')['href']
            driver.get("https://w2prod.sis.yorku.ca" + schedule_link)
            schedule_bs = BeautifulSoup(driver.page_source, "html.parser")
            tables = schedule_bs.findAll("table")
            schedule = tables[7].text

            # Get course description
            course_desc = schedule_bs.findAll("p")[3].text

            # We're about to grab the schedule, set the redundancy check
            redundant_check.setdefault(course_code + str(course_credits) + name, list())

            # Get all sections
            course_sections = tables[7].find('tbody').findAll('tr', recursive=False)
            # Some courses have no schedule at all, we will skip those
            if course_sections is None:
                # print('skipping course')
                continue
            for course_section in course_sections:
                section_info = course_section.find('tbody').findAll('tr', recursive=False)
                director = section_info[1].text.replace(
                    "Please click here to see availability.", "").replace("&nbsp;", "").replace("Section Director:", "") \
                    .strip()
                section_and_term = section_info[0].text
                section_and_term = section_and_term.split()
                # Check if we we're looking for courses in this term
                if section_and_term[1] not in SEMESTER_SET:
                    # print('skipping section')
                    continue
                section = section_and_term[3]
                term = section_and_term[1]
                course_offerings[course_code + str(course_credits) + section] = ((term,
                                                                                  course_code,
                                                                                  director,
                                                                                  section,
                                                                                  course_credits), list())
                # TODO change 'N/A' if x.strip() == '' else x.strip() to a function to make it cleaner (E.g. clean_text(lecture_info[0].text))
                for lecture_time in section_info[2].find('tbody').findAll('tr', recursive=False)[1:]:
                    lecture_info = lecture_time.findAll('td', recursive=False)
                    lecture_type = 'N/A' if lecture_info[0].text.strip() == '' else lecture_info[0].text.strip()
                    time_info = lecture_info[1].findAll('td')
                    time_string = 'N/A' if lecture_info[1].text.strip() == '' else lecture_info[1].text.strip()
                    cat = 'N/A' if lecture_info[2].text.strip() == '' else lecture_info[2].text.strip()
                    instructor = 'N/A' if lecture_info[3].text.strip() == '' else lecture_info[3].text.strip()
                    if len(time_info) >= 1:
                        day = DAY_CONVERSION['N/A' if time_info[0].text.strip() == '' else time_info[0].text]
                        start_time = 'N/A' if time_info[1].text.strip() == '' else time_info[1].text.strip()
                        duration = 'N/A' if time_info[2].text.strip() == '' else time_info[2].text.strip()
                        location = 'N/A' if time_info[3].text.strip() == '' else time_info[3].text.strip()
                        # MULTIPLE LECTURES FOR ONE SECTION
                        if len(time_info) > 4:
                            for i in range(0, (len(time_info) - 4) // 4):
                                day = day + "+" + DAY_CONVERSION[
                                    'N/A' if time_info[4 + (4 * i)].text.strip() == '' else time_info[4 + (4 * i)].text]
                                start_time = start_time + "+" + str(
                                    'N/A' if time_info[5 + (5 * i) - 1 * i].text.strip() == '' else time_info[
                                        5 + (5 * i) - 1 * i].text.strip())
                                duration = duration + "+" + str(
                                    'N/A' if time_info[6 + (6 * i) - 2 * i].text.strip() == '' else time_info[
                                        6 + (6 * i) - 2 * i].text.strip())
                                location = location + "+" + str(
                                    'N/A' if time_info[7 + (7 * i) - 3 * i].text.strip() == '' else time_info[
                                        7 + (7 * i) - 3 * i].text.strip())
                        course_offerings[course_code + str(course_credits) + section][1].append(
                            (day, location, start_time, duration, lecture_type, instructor, cat, time_string))
                    else:
                        day = 'N/A'
                        start_time = 'N/A'
                        duration = 'N/A'
                        location = 'N/A'
                        course_offerings[course_code + str(course_credits) + section][1].append(
                            (day, location, start_time, duration, lecture_type, instructor, cat, time_string))

            # Add unique course
            unique_courses[course_code + str(course_credits) + name] = (course_code,
                                                                        name,
                                                                        faculty,
                                                                        dept,
                                                                        course_desc,
                                                                        course_credits)
            go_back()

    driver.close()
    # Uncomment to add a safe guard before adding to database, helpful if you want to change schema before script finishes
    # input('add to db?')
    cnx = mysql.connector.connect(user='root',
                                  password='TESTPASSWORD',
                                  host='localhost',
                                  database='test_schema')

    cnx.autocommit = True

    cur = cnx.cursor()
    for unique_course in unique_courses.values():
        cur.execute(ADD_COURSE_QUERY, (unique_course[0],
                                       unique_course[1],
                                       unique_course[2],
                                       unique_course[3],
                                       unique_course[4],
                                       unique_course[5]))
    for k, course_offering in course_offerings.items():
        cur.execute(ADD_COURSE_OFFERING_QUERY, (
            course_offering[0][0],
            course_offering[0][1],
            course_offering[0][2],
            course_offering[0][3],
            course_offering[0][4]))
        print(course_offering[0][0], course_offering[0][1], course_offering[0][2], course_offering[0][3],
              course_offering[0][4])
        new_id = cur.lastrowid
        for time in course_offering[1]:
            cur.execute(ADD_COURSE_TIME_QUERY,
                        (time[0],
                         time[1],
                         time[2],
                         time[3],
                         time[4],
                         time[5],
                         time[6],
                         time[7],
                         new_id))
    cur.close()
    cnx.close()
except Exception:
    fd.write(format_exc(100) + "\r\n\r\n\r\n")
    fd.close()
    sys.exit(14)

fd.write("Courses scraped successfully\r\n\r\n\r\n")
fd.close()
