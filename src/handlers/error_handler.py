
class error_handler(Exception):
    def __init__(self, detail, status_code, headers=dict()):
        super().__init__(detail)
        self.status_code = status_code
        self.headers = headers