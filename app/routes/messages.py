"""
Student Direct Messaging and Project Group Chat System routes and APIs for SkillSync.
Features:
- Direct 1-to-1 persistent messaging between students
- Dedicated project team group chats with automatic creation upon member acceptance
- Group membership synchronization (active, removed)
- Real-time polling and message stream endpoints
- Protected attachment upload and download
- Unread message count badges and conversation search
"""

import os
import uuid
from datetime import datetime
from flask import Blueprint, request, session, render_template, redirect, url_for, flash, jsonify, send_from_directory, current_app
from werkzeug.utils import secure_filename
from app.models import query_db, execute_db, get_db
from app.routes.auth import login_required
from app.analytics import log_event

messages_bp = Blueprint('messages', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'txt', 'doc', 'docx', 'zip', 'py', 'js', 'json', 'html', 'css', 'md', 'csv'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def get_upload_dir():
    """Return the absolute path to the attachments upload directory, creating it if needed."""
    if os.environ.get('VERCEL'):
        upload_dir = '/tmp/skillsync_attachments'
    else:
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads', 'attachments')
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def allowed_file(filename):
    """Check if the uploaded file has a permitted extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_or_create_direct_conversation(user1_id, user2_id):
    """
    Get existing 1-to-1 conversation between user1 and user2, or create a new one.
    Guarantees no duplicate direct conversations between the same two students.
    """
    if user1_id == user2_id:
        return None

    # Check for existing conversation
    existing = query_db("""
        SELECT cp1.conversation_id
        FROM conversation_participants cp1
        JOIN conversation_participants cp2 ON cp1.conversation_id = cp2.conversation_id
        JOIN conversations c ON cp1.conversation_id = c.id
        WHERE c.conversation_type = 'direct'
          AND cp1.student_id = ?
          AND cp2.student_id = ?
    """, (user1_id, user2_id), one=True)

    if existing:
        # Re-activate participants if needed
        execute_db("""
            UPDATE conversation_participants
            SET membership_status = 'active'
            WHERE conversation_id = ? AND student_id IN (?, ?)
        """, (existing['conversation_id'], user1_id, user2_id))
        return existing['conversation_id']

    # Create new direct conversation
    conv_id = execute_db("""
        INSERT INTO conversations (conversation_type, conversation_name)
        VALUES ('direct', '')
    """)

    execute_db("""
        INSERT INTO conversation_participants (conversation_id, student_id, last_read_message_id, membership_status)
        VALUES (?, ?, 0, 'active'), (?, ?, 0, 'active')
    """, (conv_id, user1_id, conv_id, user2_id))

    return conv_id


def get_or_create_project_group(project_id):
    """
    Get existing project group conversation, or create one for the project team.
    Automatically includes project owner and all accepted team members.
    """
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project:
        return None

    existing = query_db("""
        SELECT id FROM conversations
        WHERE conversation_type = 'project_group' AND project_id = ?
    """, (project_id,), one=True)

    if existing:
        conv_id = existing['id']
    else:
        group_name = f"{project['title']} – Team Chat"
        conv_id = execute_db("""
            INSERT INTO conversations (conversation_type, project_id, conversation_name)
            VALUES ('project_group', ?, ?)
        """, (project_id, group_name))

        # Add project owner
        execute_db("""
            INSERT OR IGNORE INTO conversation_participants (conversation_id, student_id, membership_status)
            VALUES (?, ?, 'active')
        """, (conv_id, project['owner_id']))

    # Ensure all current team members are active participants
    members = query_db("SELECT user_id FROM team_members WHERE project_id = ?", (project_id,))
    for m in members:
        execute_db("""
            INSERT OR REPLACE INTO conversation_participants (conversation_id, student_id, membership_status)
            VALUES (?, ?, 'active')
        """, (conv_id, m['user_id']))

    return conv_id


def add_student_to_project_group(project_id, student_id):
    """Add an accepted student to the project's group chat and record a system welcome message."""
    conv_id = get_or_create_project_group(project_id)
    if not conv_id:
        return

    # Add or update participant to active
    execute_db("""
        INSERT OR REPLACE INTO conversation_participants (conversation_id, student_id, membership_status, joined_at)
        VALUES (?, ?, 'active', CURRENT_TIMESTAMP)
    """, (conv_id, student_id))

    # Add system notification message
    student_profile = query_db("SELECT display_name FROM student_profiles WHERE user_id = ?", (student_id,), one=True)
    s_name = student_profile['display_name'] if student_profile else "A new member"

    execute_db("""
        INSERT INTO messages (conversation_id, sender_id, message_content, message_type)
        VALUES (?, ?, ?, 'system')
    """, (conv_id, student_id, f"🎉 {s_name} has joined the team! Welcome to the project group chat."))

    execute_db("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conv_id,))


def remove_student_from_project_group(project_id, student_id):
    """Revoke a student's access to the project group chat and post a system notice."""
    existing = query_db("SELECT id FROM conversations WHERE conversation_type = 'project_group' AND project_id = ?", (project_id,), one=True)
    if not existing:
        return

    conv_id = existing['id']
    execute_db("""
        UPDATE conversation_participants
        SET membership_status = 'removed'
        WHERE conversation_id = ? AND student_id = ?
    """, (conv_id, student_id))

    student_profile = query_db("SELECT display_name FROM student_profiles WHERE user_id = ?", (student_id,), one=True)
    s_name = student_profile['display_name'] if student_profile else "A member"

    execute_db("""
        INSERT INTO messages (conversation_id, sender_id, message_content, message_type)
        VALUES (?, ?, ?, 'system')
    """, (conv_id, student_id, f"ℹ️ {s_name} was removed from the team."))

    execute_db("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conv_id,))


@messages_bp.route('/messages')
@login_required
def inbox():
    """Renders the complete 3-column messaging interface (Left list, Chat window, Info panel)."""
    user_id = session['user_id']
    selected_conv_id = request.args.get('conversation_id', type=int) or request.args.get('c', type=int)

    # Fetch user's active conversations
    conversations = query_db("""
        SELECT c.*, cp.last_read_at, cp.last_read_message_id, cp.membership_status
        FROM conversations c
        JOIN conversation_participants cp ON c.id = cp.conversation_id
        WHERE cp.student_id = ? AND cp.membership_status = 'active'
        ORDER BY c.updated_at DESC
    """, (user_id,))

    formatted_conversations = []
    for c in conversations:
        cid = c['id']
        c_type = c['conversation_type']

        # Count unread messages
        unread_row = query_db("""
            SELECT COUNT(*) as unread_count
            FROM messages m
            WHERE m.conversation_id = ?
              AND m.sender_id != ?
              AND m.id > ?
        """, (cid, user_id, c['last_read_message_id'] or 0), one=True)
        unread_count = unread_row['unread_count'] if unread_row else 0

        # Fetch last message
        last_msg = query_db("""
            SELECT m.*, sp.display_name as sender_name
            FROM messages m
            LEFT JOIN student_profiles sp ON m.sender_id = sp.user_id
            WHERE m.conversation_id = ?
            ORDER BY m.created_at DESC
            LIMIT 1
        """, (cid,), one=True)

        if c_type == 'direct':
            # Identify the other student
            other_participant = query_db("""
                SELECT u.id as user_id, u.email, sp.display_name, sp.branch, sp.year, sp.bio
                FROM conversation_participants cp
                JOIN users u ON cp.student_id = u.id
                LEFT JOIN student_profiles sp ON u.id = sp.user_id
                WHERE cp.conversation_id = ? AND cp.student_id != ?
            """, (cid, user_id), one=True)

            name = other_participant['display_name'] if other_participant and other_participant['display_name'] else (other_participant['email'] if other_participant else "Student")
            subtitle = other_participant['branch'] if other_participant and other_participant['branch'] else "Student"
            avatar_char = name[:1].upper() if name else "S"
            target_user_id = other_participant['user_id'] if other_participant else None
        else:
            # Project Group
            proj = query_db("SELECT id, title, category FROM projects WHERE id = ?", (c['project_id'],), one=True)
            name = c['conversation_name'] or (f"{proj['title']} – Team Chat" if proj else "Project Group")
            subtitle = f"Project Group • {proj['category']}" if proj else "Project Team"
            avatar_char = "👥"
            target_user_id = None

        formatted_conversations.append({
            'id': cid,
            'type': c_type,
            'name': name,
            'subtitle': subtitle,
            'avatar_char': avatar_char,
            'target_user_id': target_user_id,
            'project_id': c['project_id'],
            'unread_count': unread_count,
            'last_message': last_msg['message_content'] if last_msg else "No messages yet",
            'last_message_time': last_msg['created_at'] if last_msg else c['created_at'],
            'updated_at': c['updated_at']
        })

    # If no specific conversation selected, default to the first one if available
    active_conversation = None
    messages_list = []
    info_panel = {}

    if not selected_conv_id and formatted_conversations:
        selected_conv_id = formatted_conversations[0]['id']

    if selected_conv_id:
        # Verify access
        part = query_db("""
            SELECT * FROM conversation_participants
            WHERE conversation_id = ? AND student_id = ? AND membership_status = 'active'
        """, (selected_conv_id, user_id), one=True)

        if part:
            conv_row = query_db("SELECT * FROM conversations WHERE id = ?", (selected_conv_id,), one=True)
            active_conv_formatted = next((c for c in formatted_conversations if c['id'] == selected_conv_id), None)

            if conv_row:
                active_conversation = active_conv_formatted or {
                    'id': conv_row['id'],
                    'type': conv_row['conversation_type'],
                    'name': conv_row['conversation_name'],
                    'project_id': conv_row['project_id']
                }

                # Mark conversation as read
                max_msg = query_db("SELECT COALESCE(MAX(id), 0) as max_id FROM messages WHERE conversation_id = ?", (selected_conv_id,), one=True)
                max_id = max_msg['max_id'] if max_msg else 0
                execute_db("""
                    UPDATE conversation_participants
                    SET last_read_message_id = MAX(COALESCE(last_read_message_id, 0), ?),
                        last_read_at = CURRENT_TIMESTAMP
                    WHERE conversation_id = ? AND student_id = ?
                """, (max_id, selected_conv_id, user_id))

                # Update local unread_count for the active conversation
                for fc in formatted_conversations:
                    if fc['id'] == selected_conv_id:
                        fc['unread_count'] = 0

                # Fetch messages with attachments
                raw_messages = query_db("""
                    SELECT m.*, sp.display_name as sender_name, sp.branch as sender_branch,
                           ma.id as attachment_id, ma.file_name, ma.file_path, ma.file_type, ma.file_size
                    FROM messages m
                    LEFT JOIN student_profiles sp ON m.sender_id = sp.user_id
                    LEFT JOIN message_attachments ma ON m.id = ma.message_id
                    WHERE m.conversation_id = ?
                    ORDER BY m.created_at ASC
                """, (selected_conv_id,))

                # Deduplicate messages with attachments
                msg_map = {}
                for rm in raw_messages:
                    mid = rm['id']
                    if mid not in msg_map:
                        msg_map[mid] = {
                            'id': mid,
                            'sender_id': rm['sender_id'],
                            'sender_name': rm['sender_name'] or 'Student',
                            'sender_branch': rm['sender_branch'],
                            'is_me': (rm['sender_id'] == user_id),
                            'content': rm['message_content'],
                            'message_type': rm['message_type'],
                            'created_at': rm['created_at'],
                            'time_display': rm['created_at'][11:16] if rm['created_at'] else '',
                            'date_display': rm['created_at'][:10] if rm['created_at'] else '',
                            'attachments': []
                        }
                    if rm['attachment_id']:
                        msg_map[mid]['attachments'].append({
                            'id': rm['attachment_id'],
                            'file_name': rm['file_name'],
                            'file_type': rm['file_type'],
                            'file_size': rm['file_size']
                        })
                messages_list = list(msg_map.values())

                # Populate Right Sidebar Info
                if conv_row['conversation_type'] == 'direct':
                    other_u = query_db("""
                        SELECT u.id, u.email, sp.*
                        FROM conversation_participants cp
                        JOIN users u ON cp.student_id = u.id
                        LEFT JOIN student_profiles sp ON u.id = sp.user_id
                        WHERE cp.conversation_id = ? AND cp.student_id != ?
                    """, (selected_conv_id, user_id), one=True)

                    if other_u:
                        # Fetch other user's skills
                        skills = query_db("""
                            SELECT s.name as skill_name, ss.proficiency
                            FROM student_skills ss
                            JOIN skills s ON ss.skill_id = s.id
                            WHERE ss.user_id = ?
                        """, (other_u['id'],))

                        # Shared projects
                        shared_projects = query_db("""
                            SELECT DISTINCT p.id, p.title, p.category
                            FROM projects p
                            JOIN team_members tm1 ON p.id = tm1.project_id
                            JOIN team_members tm2 ON p.id = tm2.project_id
                            WHERE tm1.user_id = ? AND tm2.user_id = ?
                        """, (user_id, other_u['id']))

                        info_panel = {
                            'type': 'direct',
                            'user': other_u,
                            'skills': skills,
                            'shared_projects': shared_projects
                        }
                else:
                    # Project Group info
                    proj = query_db("""
                        SELECT p.*, sp.display_name as owner_name, sp.branch as owner_branch,
                               (SELECT COUNT(DISTINCT uid) FROM (
                                   SELECT p.owner_id as uid UNION SELECT user_id as uid FROM team_members WHERE project_id = p.id
                               )) as current_team_count
                        FROM projects p
                        JOIN users u ON p.owner_id = u.id
                        JOIN student_profiles sp ON u.id = sp.user_id
                        WHERE p.id = ?
                    """, (conv_row['project_id'],), one=True)

                    if proj:
                        members = query_db("""
                            SELECT u.id, sp.display_name, sp.branch, sp.year, tm.role, tm.joined_at
                            FROM team_members tm
                            JOIN users u ON tm.user_id = u.id
                            JOIN student_profiles sp ON u.id = sp.user_id
                            WHERE tm.project_id = ?
                            UNION
                            SELECT u.id, sp.display_name, sp.branch, sp.year, 'owner' as role, p.created_at as joined_at
                            FROM projects p
                            JOIN users u ON p.owner_id = u.id
                            JOIN student_profiles sp ON u.id = sp.user_id
                            WHERE p.id = ?
                            ORDER BY role DESC, display_name ASC
                        """, (proj['id'], proj['id']))

                        skills_needed = query_db("""
                            SELECT psr.*, s.name as skill_name
                            FROM project_skill_requirements psr
                            JOIN skills s ON psr.skill_id = s.id
                            WHERE psr.project_id = ?
                        """, (proj['id'],))

                        info_panel = {
                            'type': 'project_group',
                            'project': proj,
                            'members': members,
                            'skills': skills_needed
                        }

    # Fetch all students for the "New Chat" modal
    all_students = query_db("""
        SELECT u.id, u.email, sp.display_name, sp.branch, sp.year
        FROM users u
        JOIN student_profiles sp ON u.id = sp.user_id
        WHERE u.id != ? AND u.status = 'active'
        ORDER BY sp.display_name ASC
    """, (user_id,))

    return render_template(
        'messages/inbox.html',
        conversations=formatted_conversations,
        active_conversation=active_conversation,
        messages=messages_list,
        info_panel=info_panel,
        all_students=all_students
    )


@messages_bp.route('/messages/direct/<int:target_id>')
@login_required
def open_direct_message(target_id):
    """Start or open a direct 1-to-1 conversation with target student, then redirect to inbox."""
    user_id = session['user_id']
    if user_id == target_id:
        flash('You cannot message yourself.', 'warning')
        return redirect(url_for('messages.inbox'))

    target_user = query_db("SELECT id FROM users WHERE id = ?", (target_id,), one=True)
    if not target_user:
        flash('Student not found.', 'danger')
        return redirect(url_for('messages.inbox'))

    conv_id = get_or_create_direct_conversation(user_id, target_id)
    return redirect(url_for('messages.inbox', conversation_id=conv_id))


@messages_bp.route('/messages/project/<int:project_id>')
@login_required
def open_project_group(project_id):
    """Open or create a dedicated team group chat for the given project."""
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project:
        flash('Project not found.', 'danger')
        return redirect(url_for('projects.list_projects'))

    # Verify user is owner or team member
    is_owner = (project['owner_id'] == user_id)
    is_member = query_db("SELECT 1 FROM team_members WHERE project_id = ? AND user_id = ?", (project_id, user_id), one=True)

    if not (is_owner or is_member):
        flash('Access restricted: Only accepted team members can access this project group chat.', 'danger')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    conv_id = get_or_create_project_group(project_id)
    return redirect(url_for('messages.inbox', conversation_id=conv_id))


@messages_bp.route('/api/messages/<int:conversation_id>/send', methods=['POST'])
@login_required
def send_message_api(conversation_id):
    """API endpoint to post a message (with optional file attachment) into a conversation."""
    user_id = session['user_id']

    # Authorization check: must be active participant
    part = query_db("""
        SELECT * FROM conversation_participants
        WHERE conversation_id = ? AND student_id = ? AND membership_status = 'active'
    """, (conversation_id, user_id), one=True)

    if not part:
        return jsonify({'error': 'Unauthorized to send messages in this conversation.'}), 403

    if request.is_json:
        data = request.get_json() or {}
        content = data.get('content') or data.get('message_text') or data.get('message_content') or ''
        file = None
    else:
        content = request.form.get('content') or request.form.get('message_text') or request.form.get('message_content') or ''
        file = request.files.get('attachment')
    content = content.strip()

    if not content and not file:
        return jsonify({'error': 'Message content or attachment cannot be empty.'}), 400

    message_type = 'attachment' if file else 'text'

    # Insert message
    msg_id = execute_db("""
        INSERT INTO messages (conversation_id, sender_id, message_content, message_type)
        VALUES (?, ?, ?, ?)
    """, (conversation_id, user_id, content or (file.filename if file else ''), message_type))

    attachment_info = None
    if file and file.filename:
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not permitted for security reasons.'}), 400

        orig_filename = secure_filename(file.filename)
        ext = orig_filename.rsplit('.', 1)[1].lower() if '.' in orig_filename else ''
        unique_name = f"{uuid.uuid4().hex}_{orig_filename}"
        upload_path = os.path.join(get_upload_dir(), unique_name)
        file.save(upload_path)
        file_size = os.path.getsize(upload_path)

        att_id = execute_db("""
            INSERT INTO message_attachments (message_id, file_name, file_path, file_type, file_size)
            VALUES (?, ?, ?, ?, ?)
        """, (msg_id, orig_filename, unique_name, ext, file_size))

        attachment_info = {
            'id': att_id,
            'file_name': orig_filename,
            'file_type': ext,
            'file_size': file_size
        }

    # Update conversation updated_at and sender's last_read_message_id
    execute_db("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conversation_id,))
    execute_db("""
        UPDATE conversation_participants
        SET last_read_message_id = ?, last_read_at = CURRENT_TIMESTAMP
        WHERE conversation_id = ? AND student_id = ?
    """, (msg_id, conversation_id, user_id))

    # Fetch created message details
    user_profile = query_db("SELECT display_name FROM student_profiles WHERE user_id = ?", (user_id,), one=True)
    sender_name = user_profile['display_name'] if user_profile and user_profile['display_name'] else session.get('user_name', 'Student')
    msg_row = query_db("SELECT * FROM messages WHERE id = ?", (msg_id,), one=True)

    log_event('message_sent', actor_id=user_id, target_type='conversation', target_id=conversation_id)

    return jsonify({
        'success': True,
        'message': {
            'id': msg_id,
            'conversation_id': conversation_id,
            'sender_id': user_id,
            'sender_name': sender_name,
            'is_me': True,
            'content': content or (file.filename if file else ''),
            'text': content or (file.filename if file else ''),
            'message_type': message_type,
            'created_at': msg_row['created_at'],
            'time_display': msg_row['created_at'][11:16],
            'attachment': attachment_info,
            'attachments': [attachment_info] if attachment_info else []
        }
    })


@messages_bp.route('/api/messages/<int:conversation_id>/updates')
@login_required
def get_message_updates_api(conversation_id):
    """
    Real-time polling endpoint.
    Returns messages created after the specified message ID and updates read status.
    """
    user_id = session['user_id']
    after_id = request.args.get('after', 0, type=int)

    # Verify membership
    part = query_db("""
        SELECT * FROM conversation_participants
        WHERE conversation_id = ? AND student_id = ? AND membership_status = 'active'
    """, (conversation_id, user_id), one=True)

    if not part:
        return jsonify({'error': 'Unauthorized'}), 403

    raw_messages = query_db("""
        SELECT m.*, sp.display_name as sender_name,
               ma.id as attachment_id, ma.file_name, ma.file_type, ma.file_size
        FROM messages m
        LEFT JOIN student_profiles sp ON m.sender_id = sp.user_id
        LEFT JOIN message_attachments ma ON m.id = ma.message_id
        WHERE m.conversation_id = ? AND m.id > ?
        ORDER BY m.created_at ASC
    """, (conversation_id, after_id))

    # Update recipient's last_read_message_id if updates found
    if raw_messages:
        max_id = max(rm['id'] for rm in raw_messages)
        execute_db("""
            UPDATE conversation_participants
            SET last_read_message_id = MAX(COALESCE(last_read_message_id, 0), ?),
                last_read_at = CURRENT_TIMESTAMP
            WHERE conversation_id = ? AND student_id = ?
        """, (max_id, conversation_id, user_id))

    msg_map = {}
    for rm in raw_messages:
        mid = rm['id']
        if mid not in msg_map:
            msg_map[mid] = {
                'id': mid,
                'conversation_id': conversation_id,
                'sender_id': rm['sender_id'],
                'sender_name': rm['sender_name'] or 'Student',
                'is_me': (rm['sender_id'] == user_id),
                'content': rm['message_content'],
                'text': rm['message_content'],
                'message_type': rm['message_type'],
                'created_at': rm['created_at'],
                'time_display': rm['created_at'][11:16] if rm['created_at'] else '',
                'date_display': rm['created_at'][:10] if rm['created_at'] else '',
                'attachments': []
            }
        if rm['attachment_id']:
            msg_map[mid]['attachments'].append({
                'id': rm['attachment_id'],
                'file_name': rm['file_name'],
                'file_type': rm['file_type'],
                'file_size': rm['file_size']
            })

    return jsonify({
        'success': True,
        'messages': list(msg_map.values())
    })


@messages_bp.route('/api/messages/unread')
@login_required
def get_unread_counts_api():
    """Returns global and per-conversation unread message counts for client live-updating."""
    user_id = session['user_id']

    # Total unread
    total_row = query_db("""
        SELECT COUNT(*) as cnt
        FROM messages m
        JOIN conversation_participants cp ON m.conversation_id = cp.conversation_id
        WHERE cp.student_id = ?
          AND cp.membership_status = 'active'
          AND m.sender_id != ?
          AND m.id > COALESCE(cp.last_read_message_id, 0)
    """, (user_id, user_id), one=True)
    total_unread = total_row['cnt'] if total_row else 0

    # Per conversation
    per_conv = query_db("""
        SELECT m.conversation_id, COUNT(*) as cnt
        FROM messages m
        JOIN conversation_participants cp ON m.conversation_id = cp.conversation_id
        WHERE cp.student_id = ?
          AND cp.membership_status = 'active'
          AND m.sender_id != ?
          AND m.id > COALESCE(cp.last_read_message_id, 0)
        GROUP BY m.conversation_id
    """, (user_id, user_id))

    conv_map = {row['conversation_id']: row['cnt'] for row in per_conv}

    return jsonify({
        'total_unread': total_unread,
        'conversations': conv_map
    })


@messages_bp.route('/messages/attachments/<int:attachment_id>')
@login_required
def download_attachment(attachment_id):
    """Download a message attachment with participant authorization check."""
    user_id = session['user_id']

    att = query_db("""
        SELECT ma.*, m.conversation_id
        FROM message_attachments ma
        JOIN messages m ON ma.message_id = m.id
        WHERE ma.id = ?
    """, (attachment_id,), one=True)

    if not att:
        flash('Attachment not found.', 'danger')
        return redirect(url_for('messages.inbox'))

    # Verify viewer is active participant in that conversation
    part = query_db("""
        SELECT 1 FROM conversation_participants
        WHERE conversation_id = ? AND student_id = ? AND membership_status = 'active'
    """, (att['conversation_id'], user_id), one=True)

    if not part:
        return 'Unauthorized to access this attachment.', 403

    upload_dir = get_upload_dir()
    return send_from_directory(upload_dir, att['file_path'], as_attachment=True, download_name=att['file_name'])
