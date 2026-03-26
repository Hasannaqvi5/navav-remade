from app import create_app
from flask import url_for

app = create_app()
with app.test_request_context('/member/event/123'):
    rendered = app.jinja_env.get_template('base.html').render(
        current_user=None, # Mocking for speed
        request=type('MockRequest', (), {'endpoint': 'member.event_detail'})()
    )
    if 'nav-back-button' in rendered:
        print("SUCCESS: Back button found on event detail page.")
    else:
        print("FAILURE: Back button NOT found on event detail page.")

with app.test_request_context('/member/dashboard'):
    rendered = app.jinja_env.get_template('base.html').render(
        current_user=None,
        request=type('MockRequest', (), {'endpoint': 'member.dashboard'})()
    )
    if 'nav-back-button' in rendered:
        print("FAILURE: Back button found on dashboard (it should be hidden).")
    else:
        print("SUCCESS: Back button hidden on dashboard.")
