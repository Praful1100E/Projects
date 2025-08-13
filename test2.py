import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- IMPORTANT: Fill in your email details below ---

# Your email address (the sender)
sender_email = "rajputpraful791@gmail.com"

# The recipient's email address
receiver_email = "reetakrana65@gmail.com"

# Your email password or "App Password". See notes below.
# It's highly recommended to use an App Password for security.
password = "tehj edww iiqu cwgy"

# --- Create the Email Message ---

# Create the container for the message.
message = MIMEMultipart("alternative")
message["Subject"] = "Test Email from Python"
message["From"] = sender_email
message["To"] = receiver_email

# The content of your email.
text = """\
Hi,
This is a test email sent from a Python script.
It worked!
"""

# Turn the text into a proper MIME part.
part = MIMEText(text, "plain")

# Attach the text part to the message container.
message.attach(part)

# --- Send the Email ---

try:
    # Create a secure connection with the Gmail SMTP server
    # For other providers, you would change "smtp.gmail.com" and the port (587)
    server = smtplib.SMTP("smtp.gmail.com", 587)
    
    # Start TLS for security
    server.starttls()
    
    # Log in to your email account
    server.login(sender_email, password)
    
    # Send the email
    server.sendmail(sender_email, receiver_email, message.as_string())
    
    print("Email sent successfully!")

except Exception as e:
    # Print any errors that occur
    print(f"An error occurred: {e}")

finally:
    # Close the connection to the server
    if 'server' in locals() and server:
        server.quit()
