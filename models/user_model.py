class User:
    def __init__(self, username, password, preferences=None, city=None, country=None):
        self.username = username
        self.password = password
        self.preferences = preferences or []
        self.city = city
        self.country = country

    def to_dict(self):
        return {
            'username': self.username,
            'password': self.password,
            'preferences': self.preferences,
            'city': self.city,
            'country': self.country
        }