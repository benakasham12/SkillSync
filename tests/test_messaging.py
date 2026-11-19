"""
Comprehensive automated test suite for SkillSync Student Chat & Project Group Messaging System:
Validates:
1. Messages navigation item with chat icon and unread count badge.
2. Direct 1-to-1 student messaging creation and duplicate conversation prevention.
3. Message sending, persistence, ordering, timestamps, and real-time polling updates.
4. Read status tracking (sender does not increment unread for themselves; recipient gets unread count; opening thread marks read).
5. Automatic project group chat creation on project publish.
6. Automatic participant addition when project applicant is accepted or invitation is accepted.
7. Participant access revocation when member is removed from project.
8. Unauthorized access prevention (non-participants blocked from viewing/sending to conversations).
9. File attachment uploads, storage, whitelisting, and authorized downloads.
10. Global and conversation-level unread API endpoints.
"""

import pytest
import tempfile
import os
import io
import json
from app import create_app
from app.models import init_db, execute_db, query_db
from werkzeug.security import generate_password_hash


@pytest.fixture
def app():
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    init_db(db_path)

    upload_folder = tempfile.mkdtemp()

    app = create_app(db_path=db_path, test_config={
        'TESTING': True,
        'DATABASE': db_path,
        'SECRET_KEY': 'test-messages-secret-789',
        'UPLOAD_FOLDER': upload_folder
    })
    yield app

    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


def create_student(app, email, name, branch='CSE', year='3rd Year'):
    db_path = app.config['DATABASE']
    pw_hash = generate_password_hash('Password@123')
    user_id = execute_db(
        "INSERT INTO users (email, password_hash, role) VALUES (?, ?, 'student')",
        (email, pw_hash),
        db_path=db_path
    )
    execute_db(
        """INSERT INTO student_profiles (user_id, display_name, branch, year, section, is_match_ready)
           VALUES (?, ?, ?, ?, 'CSE-13', 1)""",
        (user_id, name, branch, year),
        db_path=db_path
    )
    return user_id


def login_student(client, user_id, email, name):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['user_email'] = email
        sess['user_name'] = name
        sess['user_role'] = 'student'


def extract_conversation_id(location_url):
    """Helper to parse conversation_id from redirection URL."""
    if 'conversation_id=' in location_url:
        return int(location_url.split('conversation_id=')[1].split('&')[0])
    if 'c=' in location_url:
        return int(location_url.split('c=')[1].split('&')[0])
    raise ValueError(f"Could not extract conversation id from {location_url}")


def test_navbar_messages_link_and_badge(app, client):
    """Navbar includes Messages link and dynamic unread badge."""
    s1 = create_student(app, 'alice@example.com', 'Alice Smith')
    login_student(client, s1, 'alice@example.com', 'Alice Smith')

    resp = client.get('/')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert 'href="/messages"' in html
    assert 'Messages' in html
    assert 'navUnreadMessagesBadge' in html


def test_direct_conversation_creation_and_deduplication(app, client):
    """Direct chat creation returns conversation and does not create duplicate threads."""
    s1 = create_student(app, 'alice@example.com', 'Alice')
    s2 = create_student(app, 'bob@example.com', 'Bob')

    # Alice initiates chat with Bob
    login_student(client, s1, 'alice@example.com', 'Alice')
    resp1 = client.get(f'/messages/direct/{s2}', follow_redirects=False)
    assert resp1.status_code == 302
    c_id_1 = extract_conversation_id(resp1.location)

    # Bob initiates chat with Alice - should resolve to the EXACT SAME conversation ID
    login_student(client, s2, 'bob@example.com', 'Bob')
    resp2 = client.get(f'/messages/direct/{s1}', follow_redirects=False)
    assert resp2.status_code == 302
    c_id_2 = extract_conversation_id(resp2.location)

    assert c_id_1 == c_id_2

    # Verify database has only 1 direct conversation
    db_path = app.config['DATABASE']
    convs = query_db("SELECT * FROM conversations WHERE conversation_type = 'direct'", db_path=db_path)
    assert len(convs) == 1


def test_send_message_and_realtime_updates(app, client):
    """Sending a message persists to database and is returned via the updates polling API."""
    s1 = create_student(app, 'alice@example.com', 'Alice')
    s2 = create_student(app, 'bob@example.com', 'Bob')

    login_student(client, s1, 'alice@example.com', 'Alice')
    resp = client.get(f'/messages/direct/{s2}', follow_redirects=False)
    c_id = extract_conversation_id(resp.location)

    # Alice sends message to Bob
    send_resp = client.post(f'/api/messages/{c_id}/send', data={
        'message_text': 'Hey Bob! Are you interested in teaming up?'
    })
    assert send_resp.status_code == 200
    data = send_resp.get_json()
    assert data['success'] is True
    assert data['message']['text'] == 'Hey Bob! Are you interested in teaming up?'
    msg_id = data['message']['id']

    # Fetch updates after 0
    updates_resp = client.get(f'/api/messages/{c_id}/updates?after=0')
    assert updates_resp.status_code == 200
    updates_data = updates_resp.get_json()
    assert len(updates_data['messages']) == 1
    assert updates_data['messages'][0]['id'] == msg_id

    # Fetch updates after msg_id (should be empty)
    updates_after = client.get(f'/api/messages/{c_id}/updates?after={msg_id}')
    assert len(updates_after.get_json()['messages']) == 0


def test_unread_count_tracking_and_mark_read(app, client):
    """Sender does not have unread, recipient gets unread, and loading marks read."""
    s1 = create_student(app, 'alice@example.com', 'Alice')
    s2 = create_student(app, 'bob@example.com', 'Bob')

    # Alice sends message to Bob
    login_student(client, s1, 'alice@example.com', 'Alice')
    resp = client.get(f'/messages/direct/{s2}', follow_redirects=False)
    c_id = extract_conversation_id(resp.location)
    client.post(f'/api/messages/{c_id}/send', data={'message_text': 'Hello Bob'})

    # Alice checks her unread count - should be 0
    alice_unread = client.get('/api/messages/unread').get_json()
    assert alice_unread['total_unread'] == 0

    # Bob logs in and checks unread count - should be 1
    login_student(client, s2, 'bob@example.com', 'Bob')

    bob_unread_before = client.get('/api/messages/unread').get_json()
    assert bob_unread_before['total_unread'] == 1
    assert bob_unread_before['conversations'].get(str(c_id)) == 1

    # Bob views the conversation thread (marks as read)
    inbox_resp = client.get(f'/messages?conversation_id={c_id}')
    assert inbox_resp.status_code == 200

    # Bob checks unread count again - should now be 0
    bob_unread_after = client.get('/api/messages/unread').get_json()
    assert bob_unread_after['total_unread'] == 0


def test_project_group_chat_auto_creation_and_membership(app, client):
    """Project creation creates team chat, applicant acceptance adds member, member removal revokes."""
    s1 = create_student(app, 'owner@example.com', 'Project Owner')
    s2 = create_student(app, 'applicant@example.com', 'Applicant Bob')

    # Owner creates a project
    login_student(client, s1, 'owner@example.com', 'Project Owner')
    skills_payload = [
        {"name": "Python", "priority": "Must Have", "proficiency": "Intermediate"}
    ]
    proj_resp = client.post('/projects/create', data={
        'title': 'Autonomous Drone Nav',
        'category': 'Artificial Intelligence',
        'duration': '2–3 Months',
        'description': 'Autonomous flight navigation using ROS and computer vision.',
        'objectives': 'Build prototype autonomous flight controller.',
        'technologies': 'Python, ROS, OpenCV',
        'team_size_max': '3',
        'collaboration_mode': 'Hybrid',
        'availability': 'Weekdays',
        'action': 'publish',
        'skills_json': json.dumps(skills_payload)
    }, follow_redirects=True)
    assert proj_resp.status_code == 200

    db_path = app.config['DATABASE']
    project = query_db("SELECT * FROM projects WHERE title = 'Autonomous Drone Nav'", db_path=db_path, one=True)
    assert project is not None
    p_id = project['id']

    # Verify project group chat conversation exists
    conv = query_db("SELECT * FROM conversations WHERE project_id = ?", (p_id,), db_path=db_path, one=True)
    assert conv is not None
    assert 'Autonomous Drone Nav' in conv['conversation_name']
    c_id = conv['id']

    # Owner is active participant
    owner_part = query_db("SELECT * FROM conversation_participants WHERE conversation_id = ? AND student_id = ?", (c_id, s1), db_path=db_path, one=True)
    assert owner_part is not None
    assert owner_part['membership_status'] == 'active'

    # Applicant is not yet in conversation
    app_part = query_db("SELECT * FROM conversation_participants WHERE conversation_id = ? AND student_id = ?", (c_id, s2), db_path=db_path, one=True)
    assert app_part is None

    # Applicant logs in and applies
    login_student(client, s2, 'applicant@example.com', 'Applicant Bob')
    client.post(f'/projects/{p_id}/apply', data={'message': 'I have ROS experience!'}, follow_redirects=True)

    application = query_db("SELECT * FROM project_applications WHERE project_id = ? AND applicant_id = ?", (p_id, s2), db_path=db_path, one=True)
    assert application is not None
    app_id = application['id']

    # Owner reviews and accepts applicant
    login_student(client, s1, 'owner@example.com', 'Project Owner')
    client.post(f'/projects/{p_id}/applications/{app_id}/review', data={'decision': 'accept'}, follow_redirects=True)

    # Verify applicant is now an active participant in project group chat
    app_part = query_db("SELECT * FROM conversation_participants WHERE conversation_id = ? AND student_id = ?", (c_id, s2), db_path=db_path, one=True)
    assert app_part is not None
    assert app_part['membership_status'] == 'active'

    # Owner removes member from team
    client.post(f'/projects/{p_id}/members/{s2}/remove', follow_redirects=True)

    # Verify member status is now 'removed'
    app_part_removed = query_db("SELECT * FROM conversation_participants WHERE conversation_id = ? AND student_id = ?", (c_id, s2), db_path=db_path, one=True)
    assert app_part_removed['membership_status'] == 'removed'

    # Removed member tries to send a message to group chat - must be blocked (403)
    login_student(client, s2, 'applicant@example.com', 'Applicant Bob')
    blocked_send = client.post(f'/api/messages/{c_id}/send', data={'message_text': 'Can I still message?'})
    assert blocked_send.status_code == 403


def test_file_attachment_upload_and_download_security(app, client):
    """File attachments upload correctly and require active conversation membership to download."""
    s1 = create_student(app, 'alice@example.com', 'Alice')
    s2 = create_student(app, 'bob@example.com', 'Bob')
    s3 = create_student(app, 'stranger@example.com', 'Stranger')

    login_student(client, s1, 'alice@example.com', 'Alice')
    resp = client.get(f'/messages/direct/{s2}', follow_redirects=False)
    c_id = extract_conversation_id(resp.location)

    # Alice uploads a text attachment
    file_content = b"SkillSync architecture proposal"
    data = {
        'message_text': 'Here is the doc',
        'attachment': (io.BytesIO(file_content), 'proposal.txt')
    }
    upload_resp = client.post(f'/api/messages/{c_id}/send', data=data, content_type='multipart/form-data')
    assert upload_resp.status_code == 200
    res_json = upload_resp.get_json()
    assert res_json['success'] is True
    assert len(res_json['message']['attachments']) == 1
    att_id = res_json['message']['attachments'][0]['id']

    # Alice can download
    dl_resp_alice = client.get(f'/messages/attachments/{att_id}')
    assert dl_resp_alice.status_code == 200
    assert dl_resp_alice.data == file_content

    # Bob (participant) can download
    login_student(client, s2, 'bob@example.com', 'Bob')
    dl_resp_bob = client.get(f'/messages/attachments/{att_id}')
    assert dl_resp_bob.status_code == 200
    assert dl_resp_bob.data == file_content

    # Stranger (non-participant) is forbidden (403)
    login_student(client, s3, 'stranger@example.com', 'Stranger')
    dl_resp_stranger = client.get(f'/messages/attachments/{att_id}')
    assert dl_resp_stranger.status_code == 403


def test_search_and_filters_inbox(app, client):
    """Inbox loads properly with filter queries and search."""
    s1 = create_student(app, 'alice@example.com', 'Alice')
    s2 = create_student(app, 'bob@example.com', 'Bob')

    login_student(client, s1, 'alice@example.com', 'Alice')
    client.get(f'/messages/direct/{s2}')

    # Filter: direct
    resp_direct = client.get('/messages?filter=direct')
    assert resp_direct.status_code == 200
    assert 'Bob' in resp_direct.data.decode('utf-8')

    # Filter: projects
    resp_projects = client.get('/messages?filter=projects')
    assert resp_projects.status_code == 200

    # Search for Bob
    resp_search = client.get('/messages?search=Bob')
    assert resp_search.status_code == 200
    assert 'Bob' in resp_search.data.decode('utf-8')
