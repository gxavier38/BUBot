import requests
import re
import time
import getpass
import html
from datetime import datetime

requests.packages.urllib3.disable_warnings()
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += 'HIGH:!DH:!aNULL'
try:
    requests.packages.urllib3.contrib.pyopenssl.DEFAULT_SSL_CIPHER_LIST += 'HIGH:!DH:!aNULL'
except AttributeError:
    pass

base = "https://www.bu.edu/link/bin/uiscgi_studentlink.pl/?"
moduleName = "&ModuleName="
keySem = "&KeySem="

# Constants 
fallCode = "3"
springCode = "4"
colleges = ["CAS", "CFA", "CGS", "COM", "ENG", "EOP", "GMS", "GRS", "KHC", "LAW", "MED", "MET", "OTP", "PDP", "QST", "SAR", "SDM", "SED", "SHA", "SPH", "SSW", "STH", "XRG"]

# Search 
browseModule = "reg%2Fadd%2Fbrowse_schedule.pl"
searchOption = "&SearchOptionCd=S"
collegeParam = "&College="
deptParam = "&Dept="
courseParam = "&Course="
sectionParam = "&Section="

# Signup
selectIt = "&SelectIt="
addPlannerInd = "&AddPlannerInd="

startModule = "reg%2Foption%2F_start.pl"
plannerModule = "reg%2Fplan%2Fadd_planner.pl"
preregModule = "reg%2Fprereg%2Fadd_worksheet.pl"
classModule = "reg%2Fadd%2Fconfirm_classes.pl" 

plannerScheduleModule = "reg%2Fplan%2F_start.pl" 
classScheduleModule = "reg%2Fdrop%2F_start.pl"

def getPlanner():
    planner = input("Add to planner? Enter Y or N: ").upper()
    if planner == "Y":
        planner = True
    elif planner == "N":
        planner = False
    else:
        print("Invalid planner option. Exiting")
        quit()
    return planner

def getYear():
    year = input("Enter year: ")
    try:
        yearInt = int(year)
    except:
        print("Year isn't a number. Exiting")
        quit()
    currentYear = datetime.now().year
    if currentYear - yearInt != 0 and currentYear - yearInt != -1:
        print("Year is out of range. Exiting")
        quit()
    return year
 
def getSemester():
    semester = input("Enter 1 for Fall or 2 for Spring: ")
    try:
        semester = int(semester)
    except:
        print("Semester selection isn't a number. Exiting")
        quit()
    if semester == 1:
        semester = fallCode
    elif semester == 2:
        semester = springCode
    else:
        print("Invalid semester selection. Exiting")
    return semester

def getInputs():
    planner = getPlanner()
    year = getYear()
    semester = getSemester()
    courseList = getCourses()
    username = input("Enter username: ")
    password = getpass.getpass('Enter password: ')
    return planner, year, semester, courseList, username, password

def getCourses():
    courseList = []
    print("Enter a course in format COLLEGE DEPARTMENT COURSE SECTION, e.g. \"CAS MA 108 A1\" or enter \"DONE\" to continue:")
    course = input().upper()
    while course != "DONE":
        if not isValidCourse(course):
            print("Invalid course name. Try again")
        else:
            splits = course.split(" ")
            courseList = courseList + [{"college":splits[0], "dept":splits[1], "number":splits[2], \
                "section":splits[3], "code":-1, "seats":0}]
        course = input().upper()
    return courseList

def isValidCourse(course):
    pattern = re.compile("[A-Z]{3} [A-Z]{2} [0-9]{3} [A-Z]{1,2}[0-9]{1,2}")
    if not pattern.match(course):
        return False
    splits = course.split(" ")
    if splits[0] not in colleges:
        return False
    return True

def login(session, year, semester, username, password):
    print("Logging in")
    url = base + moduleName + browseModule + searchOption + keySem + year + semester + "&College=CAS&Dept=MA&Course=108&Section=A1"
    referrer = session.get(url, verify=False).url

    result = session.post(url="https://shib.bu.edu/idp/profile/SAML2/Redirect/SSO?execution=e1s1", \
        headers={"referer":referrer}, \
        params={"j_username":username, "j_password":password, "_eventId_proceed":""} \
        ).text
    del password
    if "The username you entered cannot be identified." in result:
        print("Incorrect username. Exiting")
        quit()
    elif "The password you entered was incorrect." in result:
        print("Incorrect password. Exiting")
        quit()

    responsePattern = re.compile("value=\"[A-z0-9+]*[=]*\"")
    statePattern = re.compile("value=\"[a-z0-9&%#;]*\"")

    response = responsePattern.search(result).group(0)[7:-1]
    state = html.unescape(statePattern.search(result).group(0)[7:-1])

    result = session.post(url="https://linklogin.bu.edu/Shibboleth.sso/SAML2/POST", \
        data={"SAMLResponse":response, "RelayState":state} \
        ).text

def getSemesterName(semester):
    semester = int(semester)
    if semester == 1:
        return "Some summer"
    elif semester == 2:
        return "Some summer"
    elif semester == 3:
        return "Fall"
    elif semester == 4:
        return "Spring" 
    else:
        return "Unknown"

def getCourseCode(session, year, semester, courseList):
    print("Retrieving course codes")
    semesterName = getSemesterName(semester)
    for course in courseList:
        if course["code"] != -1:
            continue
        
        url = base + moduleName + browseModule + searchOption + keySem + year + semester + collegeParam + course["college"] \
            + deptParam + course["dept"] + courseParam + course["number"] + sectionParam + course["section"] 
        result = session.get(url).text

        coursePattern = re.compile("value=\"[0-9]*\" >.*\n.*\n.*ClassCd=" + course["college"] \
            + course["dept"] + course["number"] + "%20" + course["section"] + "&")
        try:
            code = coursePattern.search(result).group(0)[7:17]
            course["code"] = code
        except:
            print(course["college"] + " " + course["dept"] + " " + course["number"] + " " + course["section"] +" is not open for registration. Trying again later")

def start(session, year, semester):
    startUrl = base + moduleName + startModule + keySem + year + semester
    session.get(startUrl)

def checkAlreadyAdded(session, year, semester, planner, courseList):
    if planner:
        url = base + moduleName + plannerScheduleModule + keySem + year + semester
    else:
        url = base + moduleName + classScheduleModule + keySem + year + semester
    result = session.get(url).text
    
    for course in courseList[:]:
        addedPattern = re.compile(course["college"] + " " + course["dept"] + course["number"]  + " " + course["section"])
        try:
            addedPattern.search(result).group(0)
            print(course["college"] + " " + course["dept"] + " " + course["number"] + " " + course["section"] + " is already in schedule")
            courseList.remove(course)
        except:
            pass

def getSeats(session, year, semester, courseList):
    print("Searching for available seats")
    for course in courseList:
        if course["code"] == -1:
            continue

        url = base + moduleName + browseModule + searchOption + keySem + year + semester + collegeParam + course["college"] \
            + deptParam + course["dept"] + courseParam + course["number"] + sectionParam + course["section"] 
        result = session.get(url).text

        seatPattern = re.compile(str(course["code"]) + ".*\n.*\n.*\n.*.*\n.*\n.*<td\\>[ ]{1,4}[0-9]{1,3}</td>")
        seats = int(seatPattern.search(result).group(0)[-8:-5])
        course["seats"] = seats
        print("Found empty seats for " + course["college"] + " " + course["dept"] + " " + course["number"] + " " + course["section"])

def signup(session, year, semester, planner, courseList):
    print("Signing up for courses")

    # Generate urls
    if planner:
        url = base + moduleName + plannerModule + searchOption + keySem + year + semester 
    else:
        url = base + moduleName + classModule + searchOption + keySem + year + semester 

    for course in courseList:
        if course["code"] == -1:
            continue
        if course["seats"] == 0:
            continue
        url += selectIt + course["code"] 
    result = session.get(url, verify=False).text

    if "You requested a registration option not available for the semester." in result:
        print("Registration error. Registration may still be closed. Retrying") 
        return

    for course in courseList[:]:
        if course["code"] == -1:
            continue
        if course["seats"] == 0:
            continue
        addedPattern = re.compile(course["college"] + " " + course["dept"] + course["number"]  + " " + course["section"])
        try:
            addedPattern.search(result).group(0)
            print("Successfully added " + course["college"] + " " + course["dept"] + " " + course["number"] + " " + course["section"])
            courseList.remove(course)
        except:
            pass

def main():
    planner, year, semester, courseList, username, password = getInputs()

    print("-----------------------------------------")
    session = requests.session()
    login(session, year, semester, username, password)
    start(session, year, semester)
    checkAlreadyAdded(session, year, semester, planner, courseList)
    while (len(courseList) != 0):
        getCourseCode(session, year, semester, courseList)
        getSeats(session, year, semester, courseList)
        signup(session, year, semester, planner, courseList)
        time.sleep(5)

    print("Added all classes. Exiting")
    quit()

if __name__ == "__main__":
    main()
