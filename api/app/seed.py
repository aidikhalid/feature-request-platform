"""Idempotent development seed.

A reviewer should never open an empty board — an empty app looks broken even when it is
correct. Running this twice is safe: it does nothing if data already exists.
"""

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Comment, FeatureRequest, RequestStatus, User, UserRole, Vote
from app.core.security import hash_password

DEMO_PASSWORD = "Password123!"

USERS = [
    ("admin@example.com", "Ava Admin", UserRole.ADMIN),
    ("pm@example.com", "Priya Product", UserRole.ADMIN),
    ("alice@example.com", "Alice Tan", UserRole.USER),
    ("bob@example.com", "Bob Lim", UserRole.USER),
    ("carol@example.com", "Carol Wong", UserRole.USER),
    ("dan@example.com", "Dan Rahman", UserRole.USER),
]

REQUESTS = [
    ("Dark mode across the whole app", "Working late is painful on a white background. A dark theme that follows the OS setting would help a lot.", RequestStatus.PLANNED),
    ("Export reports to CSV", "We reconcile numbers in spreadsheets every month and currently retype them by hand. A CSV export on the reports screen would remove that step.", RequestStatus.IN_PROGRESS),
    ("Two-factor authentication", "Our security review flagged that we only support passwords. TOTP via an authenticator app would satisfy the requirement.", RequestStatus.UNDER_REVIEW),
    ("Bulk edit selected rows", "Changing status on forty records one at a time is slow. Let me select many and apply one change.", RequestStatus.UNDER_REVIEW),
    ("Slack notifications for status changes", "When a request I follow moves to Released, tell me in Slack rather than by email.", RequestStatus.PLANNED),
    ("Keyboard shortcuts for navigation", "Power users would like j/k to move through lists and / to focus search.", RequestStatus.UNDER_REVIEW),
    ("Mobile responsive dashboard", "The dashboard is unusable on a phone; charts overflow horizontally.", RequestStatus.IN_PROGRESS),
    ("Single sign-on with Google Workspace", "Managing separate passwords for the team is a chore and offboarding is error prone.", RequestStatus.PLANNED),
    ("Custom fields on records", "Every team tracks one or two things that do not fit the built-in fields.", RequestStatus.DECLINED),
    ("Undo for destructive actions", "Deleting is immediate and final. A ten-second undo toast would prevent a lot of support tickets.", RequestStatus.RELEASED),
    ("Search within comments", "Long threads are hard to navigate; searching inside a thread would help.", RequestStatus.UNDER_REVIEW),
    ("API rate limit headers", "We build against the API and cannot see how close we are to the limit until we hit it.", RequestStatus.RELEASED),
    ("Saved filter views", "I apply the same three filters every morning. Let me save and name that view.", RequestStatus.PLANNED),
    ("Attachment support on comments", "Screenshots explain bugs far faster than paragraphs do.", RequestStatus.UNDER_REVIEW),
    ("Weekly digest email", "A Monday summary of what changed would keep stakeholders off my back.", RequestStatus.DECLINED),
    ("Audit log for admin actions", "Compliance needs to see who changed what and when.", RequestStatus.UNDER_REVIEW),
    ("Duplicate detection when submitting", "Suggest similar existing requests while I am typing the title.", RequestStatus.UNDER_REVIEW),
    ("Public roadmap page", "Share the planned and in-progress items with customers without giving them accounts.", RequestStatus.IN_PROGRESS),
    ("Per-project permissions", "Contractors should only see the project they work on.", RequestStatus.PLANNED),
    ("Offline mode for the mobile app", "Our field staff frequently have no signal on site.", RequestStatus.DECLINED),
]

COMMENTS = [
    "Strong plus one from our team — this comes up every sprint planning.",
    "We work around this with a manual script today, but it breaks often.",
    "Would this cover the case where a record has been archived?",
    "Happy to help test this if you need a pilot team.",
    "This would save each of us roughly an hour a week.",
    "Any rough idea of timing? We are planning next quarter around it.",
    "Related to the duplicate detection request, I think.",
]

OFFICIAL_RESPONSES = {
    RequestStatus.PLANNED: "Thanks for the detail here — this is on the roadmap for next quarter. We will update this thread when work starts.",
    RequestStatus.IN_PROGRESS: "Work has started on this. We are targeting the next release and will post here when it ships.",
    RequestStatus.RELEASED: "This shipped in the latest release. Thank you to everyone who voted and commented.",
    RequestStatus.DECLINED: "We are not planning to build this for now — the maintenance cost outweighs the demand we can see. We will revisit if interest grows.",
}


def seed() -> None:
    db = SessionLocal()
    try:
        if db.execute(select(func.count()).select_from(User)).scalar_one() > 0:
            print("[seed] Database already contains data — skipping.")
            return

        users = [
            User(
                email=email,
                display_name=name,
                role=role,
                password_hash=hash_password(DEMO_PASSWORD),
            )
            for email, name, role in USERS
        ]
        db.add_all(users)
        db.flush()

        admins = [u for u in users if u.role == UserRole.ADMIN]
        rng = random.Random(42)  # Fixed seed so every reviewer sees the same board.
        now = datetime.now(timezone.utc)

        requests = []
        for index, (title, description, status) in enumerate(REQUESTS):
            request = FeatureRequest(
                title=title,
                description=description,
                status=status,
                author_id=rng.choice(users).id,
                created_at=now - timedelta(days=rng.randint(0, 40), hours=rng.randint(0, 23)),
            )
            if status in OFFICIAL_RESPONSES and index % 2 == 0:
                request.official_response = OFFICIAL_RESPONSES[status]
                request.official_response_at = now - timedelta(days=rng.randint(0, 5))
                request.official_response_by_id = rng.choice(admins).id
            requests.append(request)

        db.add_all(requests)
        db.flush()

        for request in requests:
            voters = rng.sample(users, rng.randint(0, len(users)))
            db.add_all(
                Vote(user_id=v.id, feature_request_id=request.id) for v in voters
            )
            request.vote_count = len(voters)

            commenters = rng.sample(users, rng.randint(0, 3))
            db.add_all(
                Comment(
                    feature_request_id=request.id,
                    author_id=c.id,
                    body=rng.choice(COMMENTS),
                    created_at=request.created_at + timedelta(hours=rng.randint(1, 48)),
                )
                for c in commenters
            )
            request.comment_count = len(commenters)

        db.commit()
        print(f"[seed] Created {len(users)} users and {len(requests)} feature requests.")
        print(f"[seed] Sign in as admin@example.com or alice@example.com — password: {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
