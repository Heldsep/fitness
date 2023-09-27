import argparse
import datetime
import sys
import random
import time
import base64
from urllib.parse import quote
from random_user_agent.user_agent import UserAgent

from requestium import Session

PREFIX = b'aHR0cHM6Ly9wdWJsaWVrLnVzYy5ydS5ubA=='


class FitnessBot:
    DEBUG = False
    activity_ids = None
    session = None
    username = ''
    password = ''
    date = ''  # YYYY-MM-DD
    duration = None
    start_time = ''
    end_time = ''
    select_activity_query = ''
    select_activity_referer = ''
    sleep_min = None
    sleep_max = None
    user_id = ''
    user_agent = ''
    ID = ''

    cookies = {}
    universal_headers = {}

    def __init__(self, username, password, date, start_time, activity):
        self.username = username
        self.password = password.encode('utf8')
        self.date = f'{date[-4:]}-{date[3:-5]}-{date[:2]}'
        start_datetime = datetime.datetime.strptime(start_time, '%H:%M')
        self.set_activity_params(start_datetime, activity)
        end_datetime = start_datetime + \
            datetime.timedelta(minutes=self.duration)
        self.start_time = start_datetime.strftime("%H:%M")
        self.end_time = end_datetime.strftime("%H:%M")
        self.session = Session(webdriver_path='chromedriver.exe',
                               browser='chrome',
                               default_timeout=15,
                               webdriver_options={'arguments': ['headless']})
        user_agent_rotator = UserAgent()
        self.user_agent = user_agent_rotator.get_random_user_agent()
        self.universal_headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Sec-GPC': '1',
        }

    def start(self):
        # self.wait_for_start()
        if datetime.datetime.now().strftime("%H:%M") > self.start_time:
            print('timeslot has passed!')
            return
        print(f'User-Agent set: {self.user_agent}')
        response = self.login()
        if self.DEBUG:
            f = open(f'./debug_screens/login_page.html', 'w')
            f.write(response.text)
            f.close()
        time.sleep(5)
        if response.ok and 'uitloggen' in response.text:
            print('LOGGED IN')
            auth_cookie = self.session.cookies['publiek']
            self.cookies['publiek'] = auth_cookie
            print(f'authentication cookie set: {auth_cookie}')
        else:
            print('Wrong credentials, try again')
            return

        id = self.determine_unique_ID()
        self.ID = id
        print(f'unique id set: {id}\n')

        self.select_activity_query = self.create_query()
        self.select_activity_referer = self.create_activity_referer()

        enrolled = False
        no_error = True
        no_resfreshes = 0
        print(
            f'Starting loop for {self.date}, {self.start_time} - {self.end_time}..\n------------------------------------')
        while not enrolled and no_error:

            message = f'Refreshed {no_resfreshes} times'
            sys.stdout.write("\r" + message)
            sys.stdout.flush()

            response = self.choose_activity()
            no_resfreshes += 1

            if self.DEBUG:
                f = open(f'./debug_screens/refresh{no_resfreshes}.html', 'w')
                f.write(response.text)

            # as long as no free spots, skip over this
            if f'{self.start_time}-{self.end_time}' in response.text and not 'VOL' in response.text:
                response = self.confirm_activity()
                if response.ok:
                    if 'Ingeschreven Fitness' in response.text:
                        enrolled = True
                        continue
                    else:
                        print(
                            '\nsomething went wrong, landed on wrong page\nentered wrong/invalid timeslot or this version is not linked to the given account')
                        no_error = False
                        continue

            time.sleep(random.uniform(self.sleep_min, self.sleep_max))
            if datetime.datetime.now().strftime("%H:%M") > self.start_time:
                print('\ntimeslot has passed!')
                no_error = False

        if enrolled:
            print(
                f'\n------------------------------------\nSuccessfully enrolled for Fitness!\nDate: {self.date}\nTime: {self.start_time} - {self.end_time}\nHTTP response: {response}')
            print(f'Logged out, succes met POMPEN!')
        self.logout()
###############################################
#                   ACTIONS                   #
###############################################

    def login(self):

        headers = self.universal_headers.copy()
        headers['Referer'] = f'{base64.b64decode(PREFIX).decode("ascii")}/publiek/login.php'
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        headers['Origin'] = f'{base64.b64decode(PREFIX).decode("ascii")}'

        data = {
            'username': self.username,
            'password': self.password
        }
        return self.session.post(f'{base64.b64decode(PREFIX).decode("ascii")}/publiek/login.php', headers=headers, data=data)

    def determine_unique_ID(self):
        self.session.transfer_session_cookies_to_driver()
        self.session.driver.get(
            f'{base64.b64decode(PREFIX).decode("ascii")}/publiek/laanbod.php')
        if self.DEBUG:
            f = open(f'./debug_screens/determine_page.html', 'w')
            f.write(self.session.driver.page_source)
            f.close()
        self.session.driver.ensure_element_by_xpath(
            "//i[text()='fitness']").ensure_click()
        url = self.session.driver.current_url
        unique_id = url.split('=')[1].split('_')[0]
        self.session.transfer_driver_cookies_to_session()
        return unique_id

    def choose_activity(self):

        headers = self.universal_headers.copy()
        headers['Referer'] = self.select_activity_referer

        params = (
            ('actie', 'toevoegen_linschrijving'),
            ('tabel', ''),
            ('kolom', ''),
            ('waarde', self.select_activity_query),
        )
        response = self.session.get(f'{base64.b64decode(PREFIX).decode("ascii")}/publiek/keuzelijst.php#1top',
                                    headers=headers, params=params, cookies=self.cookies)
        if self.DEBUG:
            f = open(f'./debug_screens/choose_page_unsuc.html', 'w')
            f.write(response.text)
            f.close()
        return response

    def confirm_activity(self):

        headers = self.universal_headers.copy()
        headers['Referer'] = f'{base64.b64decode(PREFIX).decode("ascii")}/publiek/bevestigen.php'
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        headers['Origin'] = f'{base64.b64decode(PREFIX).decode("ascii")}'

        data = {
            'actie': 'bevestig',
            'tabel': 'klant',
            'kolom': 'klant_id',
            'waarde': self.username
        }
        response = self.session.post(f'{base64.b64decode(PREFIX).decode("ascii")}/publiek/bevestigen.php',
                                     headers=headers, cookies=self.cookies, data=data)
        if self.DEBUG:
            f = open(f'./debug_screens/confirm_page_unsuc.html', 'w')
            f.write(response.text)
            f.close()
        return response

    def logout(self):

        headers = self.universal_headers.copy()
        headers['Referer'] = f'{base64.b64decode(PREFIX).decode("ascii")}/publiek/'

        response = self.session.get(
            f'{base64.b64decode(PREFIX).decode("ascii")}/publiek/logout.php', headers=headers, cookies=self.cookies)
        return response

    def force_stop(self):

        headers = self.universal_headers.copy()
        headers['Referer'] = f'{base64.b64decode(PREFIX).decode("ascii")}/publiek/forceer.php'

        params = (
            ('actie', 'stop'),
        )

        response = self.session.get(f'{base64.b64decode(PREFIX).decode("ascii")}/publiek/forceer.php',
                                    headers=headers, params=params, cookies=self.cookies)
        return response

###############################################
#                   UTILITY                   #
###############################################

    def create_query(self):
        return f'pack=a:6:{{s:17:"i.inschrijving_id";s:6:"{self.ID}";s:12:"jlap.pool_id";s:1:"{self.activity_ids[0]}";s:22:"jlap.j_laanbod_pool_id";s:2:"{self.activity_ids[1]}";s:7:"p.start";s:10:"{self.date}";s:12:"p.start_tijd";s:5:"{self.start_time}";s:11:"p.eind_tijd";s:5:"{self.end_time}";}}'

    def create_activity_referer(self):
        encoded_query = 'pack=' + \
            quote(
                f'a:6:{{s:17:"i.inschrijving_id";s:6:"{self.ID}";s:12:"jlap.pool_id";s:1:"{self.activity_ids[0]}";s:22:"jlap.j_laanbod_pool_id";s:2:"{self.activity_ids[1]}";s:7:"p.start";s:10:"{self.date}";s:12:"p.start_tijd";s:5:"{self.start_time}";s:11:"p.eind_tijd";s:5:"{self.end_time}";}}', safe='')
        return f'{base64.b64decode(PREFIX).decode("ascii")}/publiek/keuzelijst.php?actie=toevoegen_linschrijving&tabel=&kolom=&waarde={encoded_query}'

    def set_activity_params(self, start_datetime, activity):
        match activity:
            case 'f':
                print('Activity set to Fitness')
                self.activity_ids = (2, 47)
                self.sleep_min = 7
                self.sleep_max = 12
                self.duration = 30
            case 't':
                print('Activity set to Tennis')
                self.activity_ids = (5, 51)
                self.sleep_min = 15
                self.sleep_max = 25
                self.duration = 60
            case 's':
                print('Activity set to Squash')
                self.activity_ids = (6, 48)
                self.sleep_min = 10
                self.sleep_max = 20
                self.duration = 45
            case _:
                raise ValueError(f'activity {activity} not yet implemented')


def main(args):
    bot = FitnessBot(username=args.username, password=args.password,
                     date=args.date, start_time=args.time, activity=args.activity)
    bot.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="""
  This script is going to repeatedly try to enroll for Fitness at RSC. 
  """)
    parser.add_argument("username", help="your studentnumber")
    parser.add_argument("password", help="corresponding password")
    parser.add_argument("date", help="the date (DD-MM-YYYY, e.g. 18-12-2021)")
    parser.add_argument("time", help="the time (HH:MM, e.g. 09:30)")
    parser.add_argument(
        "activity", help="desired activity (f for fitness, t for tennis)")

    args = parser.parse_args()
    main(args)
