class Slot:
    def __init__(self, date, time, available=True, booked_by=None):
        self.date = date
        self.time = time
        self.available = available
        self.booked_by = booked_by
    
    def __str__(self):
        status = "Available" if self.available else f"Booked by {self.booked_by}"
        return f"{self.date} at {self.time} - {status}"


class Booking:
    def __init__(self, user_name, date, time, booking_id=None, booking_date=None):
        self.user_name = user_name
        self.date = date
        self.time = time
        self.booking_id = booking_id
        self.booking_date = booking_date
    
    def __str__(self):
        return f"Booking #{self.booking_id}: {self.user_name} on {self.date} at {self.time}"