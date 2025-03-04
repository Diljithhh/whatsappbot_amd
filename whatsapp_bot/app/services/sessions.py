from datetime import datetime
from typing import Dict

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}

    def get_session(self, phone_number: str) -> Dict:
        if phone_number not in self.sessions:
            self.sessions[phone_number] = {
                "phone_number": phone_number,
                "start_time": datetime.now(),
                "context": [],
                "last_message": None
            }
        return self.sessions[phone_number]

    def update_context(self, phone_number: str, message: str, role: str = "user"):
        session = self.get_session(phone_number)
        session["context"].append({
            "role": role,
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        session["last_message"] = datetime.now()
