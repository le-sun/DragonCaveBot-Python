import requests
from bs4 import BeautifulSoup as soup

from dragcavebot.dragons import dragons_description_to_name


class DragCave:
    base_url = "https://dragcave.net"
    COAST = f"{base_url}/locations/1"
    DESERT = f"{base_url}/locations/2"
    FOREST = f"{base_url}/locations/3"
    JUNGLE = f"{base_url}/locations/4"
    ALPINE = f"{base_url}/locations/5"
    VOLCANO = f"{base_url}/locations/6"
    LOCATIONS = (COAST, DESERT, FOREST, JUNGLE, ALPINE, VOLCANO)
    WANTED_EGGS = {}

    def set_wanted_eggs(self, eggs):
        self.WANTED_EGGS = {**eggs}

    def login(self, user, password):
        login_url = f"{self.base_url}/login"
        login_res = requests.post(
            login_url,
            data={
                "username": user,
                "password": password
            },
            timeout=5
        )
        login_page = soup(login_res.content, 'lxml')
        if login_page.find_all(string=user):
            login_post_res = login_res.history[0]
            self.cookies = login_post_res.cookies
            return True
        return False

    def logout(self):
        print("Logging out")
        # Temp logout
        res = requests.get(
            f"{self.base_url}/logout",
            cookies=self.cookies,
        )

        # request = requests.Request(
        #     "POST",
        #     f"{self.base_url}/account/sessions",
        #     files={
        #         "logout": self.cookies["s"]
        #     },
        #     cookies=self.cookies,
        #     headers={
        #         "Content-Type": "application/x-www-form-urlencoded"
        #     }
        # ).prepare()
        # session = requests.Session()
        # res = session.send(request)
        # res = requests.post(
        #     f"{self.base_url}/account/sessions",
        #     files=dict(logout=self.cookies["s"]),
        #     cookies=self.cookies,
        #     headers={
        #         "Content-Type": "application/x-www-form-urlencoded"
        #     }
        # )
        # print(res.content)
        # print(res.status_code)
        print("Logged out")

    def get_available_eggs(self, location):
        eggs = []
        try:
            res = requests.get(
                location,
                cookies=self.cookies,
                timeout=3
            )
            page = soup(res.content, "lxml")
            egg_section = page.find("div", {"class": "eggs"})
            for egg in egg_section.children:
                egg_link = egg.a["href"]
                egg_description = egg.text
                name = dragons_description_to_name.get(egg_description, None)
                if self.WANTED_EGGS.get(name, None):
                    egg_result = self.get_egg(egg_link)
                    eggs.append((name, egg_result))
        except requests.exceptions.ReadTimeout as e:
            print(e)
        except Exception as e:
            print(e)
        return eggs

    def get_egg(self, egg_link):
        get_egg_url = f"{self.base_url}{egg_link}"
        print(get_egg_url)
        try:
            res = requests.post(
                get_egg_url,
                cookies=self.cookies,
            )
            egg_result = self.get_egg_result(soup(res.content, "lxml"))
            return egg_result
        except requests.exceptions.ReadTimeout as e:
            print(e)
            return "Error"

    def get_egg_result(self, content):
        try:
            is_overburdened = content.find_all(string="You are already overburdened and decide not to stress yourself by taking this egg")
            is_late = content.find_all(string="Sorry, this egg has already been taken by somebody else.")

            if is_overburdened:
                return is_overburdened[0]

            if is_late:
                return is_late[0]

            return "Collected"

        except Exception as e:
            print(e)
            return "Error"
