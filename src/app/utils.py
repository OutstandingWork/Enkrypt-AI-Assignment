def validate_booking_request(request_data):
    """
    Validates the booking request data.
    
    Parameters:
    - request_data (dict): The data from the booking request.

    Returns:
    - bool: True if the request is valid, False otherwise.
    - str: An error message if the request is invalid, otherwise an empty string.
    """
    if 'date' not in request_data or 'slots' not in request_data:
        return False, "Missing required fields: 'date' and 'slots'."
    
    if not isinstance(request_data['slots'], list) or len(request_data['slots']) == 0:
        return False, "Slots must be a non-empty list."
    
    # Additional validation logic can be added here

    return True, ""


def format_booking_response(booking_data):
    """
    Formats the booking response data for the user.

    Parameters:
    - booking_data (dict): The data related to the booking.

    Returns:
    - dict: A formatted response containing booking details.
    """
    return {
        "status": "success",
        "message": "Booking successful!",
        "booking_details": booking_data
    }