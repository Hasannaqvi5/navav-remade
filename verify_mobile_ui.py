from app import create_app
app = create_app()

class MockUser:
    is_authenticated = True
    display_name = "Test User"
    memberships = []

with app.test_request_context('/'):
    rendered = app.jinja_env.get_template('base.html').render(
        current_user=MockUser(),
        request=type('MockRequest', (), {'endpoint': 'member.dashboard'})()
    )
    # Check if emojis are gone
    emojis = ["🏠", "📊", "⚙️", "👤", "🏢", "🚪"]
    for e in emojis:
        if e in rendered:
            print(f"FAILURE: Emoji {e} still present in mobile menu.")
    
    # Check if header styles are updated
    if "var(--text-muted)" in rendered:
        print("SUCCESS: Header styles updated to use var(--text-muted).")
    else:
        print("FAILURE: Header styles not updated.")

# Check CSS
with open('c:/Users/Hasan/.gemini/antigravity/scratch/navres-attendance/app/static/css/main.css', 'r', encoding='utf-8') as f:
    css = f.read()
    if ".nav-mobile {" in css and "background: #fff;" in css:
        print("SUCCESS: .nav-mobile background updated to #fff.")
    if ".nav-mobile-link {" in css and "color: var(--navy);" in css:
        print("SUCCESS: .nav-mobile-link color updated to var(--navy).")
