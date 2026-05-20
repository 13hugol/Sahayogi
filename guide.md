# Sahayogi Build Rulebook

This guide is prescriptive. It defines how the Sahayogi project must be planned, built, tested, documented, and presented for the Integrative Project module. It is not a description of the current codebase.

Source inputs used for this rulebook:

- `Documents/Sahayogi_Final-592d26c2-3158-4720-8a1b-4f2fe5ea00cc.pdf`
- `Documents/Sahayogi_userstry (1).xlsx`
- The module rules and Flask OOP teaching material provided in the task brief

## 1. Product Rule

Sahayogi must be a web-based, credit-based skill sharing platform. A user must be able to teach a skill to earn internal credits, then spend credits to learn a different skill from another user. The system must not depend on direct cash payment or one-to-one barter.

The name Sahayogi means helper or collaborator in Nepali, so the product must feel like a trusted community for practical peer learning, not like a normal ecommerce marketplace.

The product must solve this problem: many learners cannot afford paid platforms, while many people already have useful skills but no structured way to teach, receive value, schedule sessions, communicate, and build trust.

## 2. Non-Negotiable Scope

The project must include:

- Secure registration, email verification, login, logout, password reset, and account protection.
- User profiles with skills offered, skills wanted, location, avatar, bio, reputation, certificates, and review history.
- Skill listings with categories, descriptions, availability, credit cost, search, filters, saved listings, and admin approval.
- Learning or exchange requests where learners apply and teachers accept or reject.
- Internal credit balances, credit transfer, and a complete credit transaction ledger.
- In-app messaging, notifications, unread message badges, and video call support for active exchanges.
- Reviews, ratings, reputation scores, reports, and admin moderation.
- Admin dashboard, user suspension or ban, role-based access control, category management, listing approval, audit logs, and GDPR-style account deletion.

The project must exclude:

- Real money payments, payment gateways, deposits, withdrawals, and external financial transactions.
- Advanced AI recommendations or predictive matching.
- Third-party automated certificate verification APIs.
- Social media login and external social sharing.
- Full multilingual localization beyond the current English interface.
- Complex gamification such as badges, levels, streaks, or experience points.

Priority controls delivery order. It does not remove a story from scope unless the team formally records a descoping decision in sprint evidence.

## 3. Module Rules

The Integrative Project is a 20 credit, Level 4, 13 week module. The project must show that the team can integrate first-year learning from programming, algorithms, databases, computer systems, and legal, ethical, social, and professional issues.

The team must evidence these learning outcomes:

- Carry out an Agile project using sprints, scrums, sprint boards, and review evidence.
- Apply programming, database, and computer systems knowledge in working software.
- Demonstrate communication, conflict resolution, teamwork, time management, written presentation, verbal presentation, and critical reflection.
- Use professional practices such as version control, testing, risk management, documentation, and LESPI analysis.

The required development environment is:

- IDE: Visual Studio Code.
- Backend: Python 3 and Flask.
- GUI: Jinja templates with HTML, CSS, Bootstrap, and vanilla JavaScript.
- Database: MySQL managed through MySQL Workbench.
- Version control: Git and GitHub.
- Testing: pytest plus manual browser testing evidence.

## 4. Agile Working Rules

The project must use an Agile Scrum-inspired approach. The team must work in short iterations, hold regular progress checks, review completed stories, and adapt the backlog based on evidence.

Each sprint must produce:

- Sprint goal.
- Selected user stories.
- Task breakdown.
- Assigned owner or pair.
- Estimated effort or story points.
- Daily or regular scrum notes.
- Evidence of progress in a board such as Trello.
- Git commits linked to the work completed.
- Testing evidence before merge.
- Sprint review notes.
- Sprint retrospective with at least one improvement action.

Definition of Ready:

- The user story has a clear actor, action, and benefit.
- Acceptance criteria are written and testable.
- Required database tables or fields are identified.
- Required routes, controllers, templates, and model methods are identified.
- Security, privacy, and role access impact is considered.

Definition of Done:

- The story works through the browser using Jinja pages or required JSON endpoints.
- Data is persisted correctly in MySQL.
- Access control is enforced on the backend, not only hidden in the UI.
- Form validation and error handling are present.
- Tests or clear manual test evidence exist.
- No plain-text passwords, unsafe SQL, or unprotected admin actions are introduced.
- The sprint board and documentation are updated.

## 5. Required Architecture

The project must follow an MVC structure with object-oriented route registration.

- Model: owns database queries and data rules.
- View: owns Jinja templates and static assets.
- Controller: owns business logic, form processing, redirects, flash messages, and calls to models.
- Routes: map URLs to controller methods using Flask Blueprints.

Do not place business logic in templates. Do not place raw SQL in templates. Do not place all routes in `run.py` or one large application file.

### Required Folder Structure

```text
Sahayogi/
    run.py
    config.py
    requirements.txt
    app/
        __init__.py
        database.py
        auth.py
        models/
            base_model.py
            user.py
            profile.py
            category.py
            skill.py
            exchange_request.py
            exchange.py
            message.py
            notification.py
            review.py
            report.py
            credit_transaction.py
            admin_audit.py
        controllers/
            base_controller.py
            auth_controller.py
            profile_controller.py
            skill_controller.py
            request_controller.py
            exchange_controller.py
            message_controller.py
            notification_controller.py
            review_controller.py
            credit_controller.py
            admin_controller.py
        routes/
            auth_routes.py
            profile_routes.py
            skill_routes.py
            request_routes.py
            exchange_routes.py
            message_routes.py
            notification_routes.py
            review_routes.py
            credit_routes.py
            admin_routes.py
        templates/
            base.html
            errors/
            auth/
            profiles/
            skills/
            requests/
            exchanges/
            messages/
            notifications/
            reviews/
            credits/
            admin/
        static/
            css/
            js/
            images/
            uploads/
```

The names may be adjusted, but the separation of `models`, `controllers`, `routes`, `templates`, and `static` must remain.

## 6. Configuration Rules

All environment-dependent settings must live in `config.py`. Application code must import configuration from there rather than hardcoding secrets, database credentials, upload limits, or mail settings.

Minimum required settings:

```python
SECRET_KEY = "change-this-to-a-random-secret-key"

MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASSWORD = "root"
MYSQL_DATABASE = "sahayogi"

MAIL_SERVER = "smtp.gmail.com"
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = ""
MAIL_PASSWORD = ""

UPLOAD_FOLDER = "app/static/uploads"
MAX_AVATAR_SIZE_MB = 5
MAX_CERTIFICATE_SIZE_MB = 10
DEFAULT_TEACHING_CREDIT_REWARD = 10
```

Rules:

- `SECRET_KEY` must be random and secret outside development.
- MySQL database name must be created before the app starts.
- Upload limits must be enforced in backend validation.
- Email tokens must expire: verification tokens and deletion confirmations may use their own expiry, password reset tokens must expire within 30 minutes.
- Development may log email links locally, but the feature logic must still be implemented as if real email is configured.

## 7. Application Factory Rules

`run.py` must stay small. It must import `create_app()` and start the development server.

```python
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
```

`app/__init__.py` must define `create_app()` and handle all application setup:

- Create the Flask app.
- Load configuration.
- Set the secret key.
- Initialize or verify database tables.
- Register CSRF protection.
- Register Blueprints.
- Register custom error handlers.
- Return the configured app.

Required flow:

```text
create Flask app
load config
initialize database
set request protections
register blueprints
register error handlers
return app
```

`debug=True` is allowed only in development. Production or final deployment documentation must explain that debug mode should be off.

## 8. Blueprint and Route Rules

Every feature area must have its own route class and Blueprint. Route files must not contain the main business logic; they must call controller methods.

Required route pattern:

```python
from flask import Blueprint
from app.auth import login_required, admin_required
from app.controllers.skill_controller import SkillController

class SkillRoutes:
    def __init__(self):
        self.bp = Blueprint("skills", __name__)
        self.controller = SkillController()

    def register(self):
        self.bp.route("/skills")(login_required(self.controller.list_skills))
        self.bp.route("/skills/new", methods=["GET", "POST"])(
            login_required(self.controller.create_skill)
        )
        self.bp.route("/skills/<int:skill_id>")(
            login_required(self.controller.detail)
        )
        return self.bp
```

Required protection rules:

- Public pages may include home, register, login, public top-rated users, and public listing previews if the team chooses.
- User pages must use `login_required`.
- Admin pages must use `admin_required`.
- Every POST route must validate CSRF.
- Every sensitive action must check authorization inside the backend route or controller.

## 9. Request Lifecycle Rules

Every request must follow this pattern:

```text
User visits URL
before_request creates or validates CSRF token
Blueprint matches the route
Decorator checks login or admin access
Controller validates input and calls models
Model reads or writes MySQL
Controller flashes message and returns template or redirect
User sees updated page
```

GET and POST rules:

- GET must show data or forms. It must not create, update, or delete records.
- POST must handle form submissions and state changes.
- POST must validate CSRF, permissions, and form fields.
- Successful POST actions should usually redirect to avoid duplicate form submission on refresh.

## 10. Database Rules

The taught architecture requires a single database access class in `app/database.py`. Model classes must use this class or an equivalent central data layer. Do not create new MySQL connections directly inside controllers or templates.

Required database class behavior:

```python
import pymysql
import config

class Database:
    def __init__(self):
        self.__connection = pymysql.connect(
            host=config.MYSQL_HOST,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DATABASE,
            cursorclass=pymysql.cursors.DictCursor,
        )

    def fetch_one(self, query, params=None):
        cursor = self.__connection.cursor()
        cursor.execute(query, params)
        result = cursor.fetchone()
        cursor.close()
        return result

    def fetch_all(self, query, params=None):
        cursor = self.__connection.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()
        cursor.close()
        return results

    def execute(self, query, params=None):
        cursor = self.__connection.cursor()
        cursor.execute(query, params)
        self.__connection.commit()
        cursor.close()

    def close(self):
        self.__connection.close()
```

SQL rules:

- Use parameterized queries with `%s` placeholders.
- Never build SQL by concatenating user input.
- Use `DictCursor` so rows are accessed by field name.
- Close database connections after use.
- Keep reusable queries inside model methods.
- Credit transfers must be atomic: debit, credit, and transaction history must succeed together or fail together.

## 11. Required Data Model

The MySQL schema must support these entities.

| Entity | Purpose |
| --- | --- |
| `users` | Login identity, role, email verification, lockout, suspension, ban, deletion state |
| `profiles` | Avatar, location, bio, skills offered, skills wanted, reputation display fields |
| `categories` | Admin-managed skill categories such as Tech, Music, Language, Kitchen |
| `skills` | Skill listings, category, description, availability, credit cost, approval status |
| `saved_listings` | User bookmarks for listings |
| `certificates` | Uploaded certificate files and admin verification status |
| `exchange_requests` | Learner application, teacher decision, optional decline reason |
| `exchanges` | Accepted learning sessions, status, completion, video session summary |
| `conversations` | Message thread tied to accepted exchanges or matches |
| `messages` | Text messages, delivered/read status, timestamps |
| `notifications` | Bell notifications with read state and target links |
| `reviews` | Star ratings and comments after completed exchanges |
| `reports` | User reports for spam, harassment, fake profile, fraud, or other |
| `credit_transactions` | Full ledger of credit debits, credits, refunds, and rewards |
| `admin_audit_logs` | Admin actions such as approve, reject, suspend, ban, role change |
| `password_reset_tokens` | One-time password reset tokens expiring within 30 minutes |
| `email_verification_tokens` | Account activation tokens |

Required statuses:

- User status: `active`, `locked`, `suspended`, `banned`, `deleted`.
- Listing status: `pending`, `approved`, `rejected`, `deactivated`.
- Certificate status: `none`, `pending`, `approved`, `rejected`.
- Request status: `pending`, `accepted`, `declined`, `cancelled`.
- Exchange status: `active`, `completed`, `cancelled`.
- Report status: `open`, `reviewing`, `resolved`, `dismissed`.

## 12. Product Workflow Rules

The core workflow must work like this:

1. User registers with name, email, password, and location.
2. System sends verification email.
3. User verifies email and sets up profile.
4. User posts a skill listing with category, description, availability, and credit cost.
5. Listing enters `pending` status.
6. Admin approves or rejects the listing.
7. Learner browses, searches, filters, and opens a listing.
8. Learner sends a request and optional message.
9. Teacher accepts or declines the request.
10. Accepted request creates an exchange and opens messaging.
11. Learner and teacher communicate and may start an in-app video call.
12. Exchange is marked completed.
13. Credits are transferred and ledger entries are recorded.
14. Both users may leave reviews.
15. Reputation score updates from received reviews.

Credit rules:

- A learner must not start a credit-based request without enough credits.
- The ledger must show date, action, skill, linked exchange, and credit change.
- Default teaching reward is 10 credits unless a listing defines another cost.
- Every credit change must have a matching transaction record.
- Admins must not edit balances silently; corrections must be logged.

## 13. Security and LESPI Rules

Security:

- Passwords must be hashed using bcrypt or an equivalent secure hashing method with a cost factor of at least 10.
- Plain-text passwords must never be stored, logged, emailed, or displayed.
- Failed login attempts must be counted; after three consecutive failures, the account must lock for 10 minutes.
- Sessions must be invalidated on logout, ban, suspension, and account deletion.
- Admin routes must return 403 for non-admin users.
- CSRF protection must apply to every POST form.
- Uploaded files must validate extension, MIME type, size, and storage path.

Privacy and GDPR:

- Account deletion must be available in profile settings.
- Deletion must require password confirmation.
- Personal data must be deleted or anonymized within 30 days.
- Aggregated or anonymized review records may remain for platform integrity.
- The system must store only the personal data needed for the platform.

Ethical and social responsibilities:

- The credit system must be fair and transparent.
- Users must be able to report abuse.
- Admin moderation must have audit logs.
- Trust indicators such as reviews, reputation, and certificate badges must not be misleading.
- The interface must be usable by normal students and low-income learners, not only technical users.

## 14. UI and Jinja Rules

The interface must be built with Jinja templates, HTML, CSS, Bootstrap, and vanilla JavaScript.

Required UI principles:

- Use a shared `base.html` with navigation, flash messages, CSRF hidden input support, and common layout.
- Navigation must show login/register for guests and dashboard/profile/messages/notifications/logout for logged-in users.
- Admin links must be hidden from regular users, but backend access control must still enforce security.
- Forms must show inline validation errors.
- Success and failure messages must be clear.
- Listing cards must show title, category, poster name, reputation, exchange type or credit cost, and badge state.
- Profiles must show avatar, location, bio, skills, reviews, completed exchanges, certificates, and reputation.
- Empty states must be helpful: no listings, no messages, no reviews, no matches, no notifications.
- Pages must be responsive for laptop and mobile widths.

JSON endpoints are allowed for dynamic UI features such as unread badge count, notifications, and search suggestions, but the main graphical interface must be Jinja-rendered.

## 15. Required User Stories

All 30 stories below are requirements. The epic IDs and priorities come from the Agile spreadsheet.

### F1 - Identity and Security

#### US-01 / F1-1.1 - Register Account - High

As a new user, I want to register an account so that I can access the skill exchange platform.

Acceptance criteria:

- Registration form requires full name, email, password, and location fields; all are mandatory.
- System validates email format and shows an inline error if invalid or already in use.
- User receives a verification email and must confirm before the account is activated.
- Successful registration redirects user to a profile setup page with a welcome message.

#### US-02 / F1-1.2 - Login and Logout - High

As a registered user, I want to log in and log out securely so that my account remains protected.

Acceptance criteria:

- Login accepts valid email and password; incorrect credentials display a clear error message.
- Session is maintained across pages; user remains logged in until they explicitly log out.
- Logout button is accessible from all pages and immediately invalidates the session or token.
- After three consecutive failed attempts, the account is temporarily locked for 10 minutes.

#### US-03 / F1-1.3 - Password Security - High

As a user, I want my password to be securely hashed so that my credentials are protected even if the database is compromised.

Acceptance criteria:

- Passwords are hashed using bcrypt or equivalent with a minimum cost factor of 10 before storage.
- Plain-text passwords are never stored or logged anywhere in the system.
- Password reset generates a one-time secure token sent via email, expiring within 30 minutes.
- Users can change their password from profile settings by confirming their current password first.

#### US-27 / F1-1.4 - Permanent Account Deletion - High

As a user, I want to permanently delete my account and data so that I can exercise my GDPR rights.

Acceptance criteria:

- Account deletion option is available in profile settings; initiating it requires password confirmation.
- Upon deletion, all personal data such as name, email, bio, messages, and listings is permanently removed or anonymized within 30 days.
- User receives a final confirmation email after deletion is processed.
- Aggregated or anonymized data, such as review text attributed to `Deleted User`, may be retained for platform integrity.

### F2 - Profile and Trust

#### US-04 / F2-2.1 - Profile Page - High

As a user, I want a profile page that displays my information and skills so that others can learn about me.

Acceptance criteria:

- Profile page shows avatar, name, location, bio, skills offered, skills wanted, and reputation score.
- Verified skill certificates are indicated with a badge next to the relevant skill.
- Profile is publicly viewable by other logged-in users; visitors see a prompt to register.
- Review history and total completed exchanges are visible on the profile page.

#### US-05 / F2-2.2 - Edit Profile - Medium

As a user, I want to edit my profile so that I can keep my information and skills up to date.

Acceptance criteria:

- Edit profile form pre-fills with existing data; user can update name, bio, avatar, and location.
- Skills offered and skills wanted can be added or removed individually without clearing other fields.
- Changes are saved with a success notification; unsaved changes prompt a confirmation before leaving.
- Avatar upload accepts JPG or PNG under 5MB and displays a cropped preview before saving.

#### US-17 / F2-2.3 - Report User - High

As a user, I want to report another user so that the platform remains safe and respectful.

Acceptance criteria:

- A `Report User` button is accessible from any user's public profile page.
- Report form requires selecting a reason: spam, harassment, fake profile, fraud, or other; description is optional.
- Submitted reports are sent to admin review; reporter receives confirmation that the report was received.
- A user cannot submit duplicate reports against the same user within a 7-day window.

#### US-18 / F2-2.4 - Leave Review - Medium

As a user, I want to leave a review after an exchange so that others can make informed decisions.

Acceptance criteria:

- Review form appears only after both parties have marked an exchange as completed.
- Review requires a star rating from 1-5 and an optional written comment of up to 500 characters.
- Submitted reviews are published immediately on the reviewed user's profile.
- Users can only leave one review per completed exchange; submitted reviews cannot be deleted by the reviewer.

#### US-19 / F2-2.5 - Reputation Score - Medium

As a user, I want to see a reputation score on each profile so that I can assess trustworthiness at a glance.

Acceptance criteria:

- Reputation score is calculated as the average of all received star ratings rounded to one decimal place.
- Score is displayed prominently on the profile page and on all listing or match cards.
- Score updates automatically within 24 hours of a new review being submitted.
- Profiles with fewer than 3 reviews display `New Member` instead of a numeric score.

#### US-20 / F2-2.6 - Review History - Low

As a user, I want to view a review history page so that I can read all feedback for a particular user.

Acceptance criteria:

- Review history page lists all reviews received by a user in reverse chronological order.
- Each review entry shows reviewer name, star rating, comment, and submission date.
- Page is accessible from the user's profile through a `View All Reviews` link.
- Reviews are paginated to show 10 per page with navigation controls.

#### US-22 / F2-2.7 - Top-Rated Users - Low

As a user, I want to see a top-rated users page so that I can quickly find highly trusted community members.

Acceptance criteria:

- Top-rated page displays users ranked by reputation score in descending order.
- Only users with 3 or more completed reviews are eligible to appear on this page.
- Each entry shows avatar, name, reputation score, top skill category, and a link to their profile.
- Page refreshes rankings daily and is publicly accessible without login.

#### US-28 / F2-2.8 - Certificate Upload - Low

As a user, I want to upload a certificate to verify my skills so that others can trust my expertise.

Acceptance criteria:

- Skill listing form includes an optional certificate upload field accepting PDF or image files up to 10MB.
- Uploaded certificates are sent to admin for manual review; listing shows `Verification Pending` badge until approved.
- Approved certificates display a `Verified` badge on the listing and the user's profile.
- Users can replace or remove a certificate from their listing at any time, which resets verification status.

### F3 - Listings and Discovery

#### US-06 / F3-3.1 - Post Skill Offer - High

As a user, I want to post a skill offer so that others can find and request my expertise.

Acceptance criteria:

- Skill listing form requires title, category, description, exchange type, and availability.
- Listing is saved as `pending` and sent for admin approval before appearing in public search results.
- User can edit or delete their own listings from a personal listings management page.
- Each listing displays the poster's reputation score and verified badge status alongside the offer.

#### US-07 / F3-3.2 - Browse Skill Listings - High

As a user, I want to browse all available skill listings so that I can discover what others are offering.

Acceptance criteria:

- Listings page displays cards with skill title, category, poster name, reputation, and exchange type.
- Default view shows the most recently approved listings; pagination limits results to 20 per page.
- Each listing card links to a detailed view showing full description, availability, and contact option.
- Users can save or bookmark listings and access them from a dedicated saved-listings section.

#### US-08 / F3-3.3 - Keyword Search - Medium

As a user, I want to search skills by keyword so that I can quickly find specific expertise I need.

Acceptance criteria:

- Search bar is visible on the browse page and returns results matching title or description keywords.
- Search results update dynamically or on submit and display the number of results found.
- Partial keyword matching is supported, for example `guitar` returns `guitarist` and `guitar lessons`.
- If no results are found, a friendly message is shown with suggestions to broaden the search.

#### US-09 / F3-3.4 - Category Filter - Medium

As a user, I want to filter skill listings by category so that I can narrow down results to my area of interest.

Acceptance criteria:

- Filter options include at minimum Tech, Music, Language, and Kitchen categories.
- Multiple categories can be selected simultaneously; results show listings matching any selected category.
- Active filters are displayed as removable tags above the results list.
- Applying a filter preserves any active keyword search and combines both conditions.

#### US-10 / F3-3.5 - Skill Categories - Low

As a user, I want skills to be organized into clear categories so that the platform remains easy to navigate.

Acceptance criteria:

- Each skill listing must be assigned exactly one primary category from the predefined list.
- Category icons or labels are displayed on listing cards for quick visual identification.
- A category overview page shows the count of active listings per category.
- Admin can add or rename categories without requiring code deployment.

#### US-30 / F3-3.6 - Location Filter - Low

As a user, I want to filter skill listings by location so that I can find nearby exchange partners.

Acceptance criteria:

- Location filter allows users to enter a city or region or use their device's detected location.
- Results are filtered to show listings from users within a configurable radius, for example 10km, 50km, or 100km.
- Distance from the user's location is displayed on each listing card in the filtered results.
- Location filter can be combined with keyword search and category filters simultaneously.

### F4 - Exchange and Communication

#### US-11 / F4-4.1 - Mutual Skill Matches - High

As a user, I want to see mutual skill matches so that I can find people whose needs align with my offerings.

Acceptance criteria:

- Mutual match finder compares my skills offered against others' skills wanted and vice versa.
- Matched users are shown in a dedicated `Matches` section sorted by match relevance score.
- Each match card shows overlapping skills, the other user's reputation score, and a contact button.
- User is notified via in-app notification when a new mutual match is detected.

#### US-12 / F4-4.2 - Accept or Decline Requests - High

As a user, I want to accept or decline skill exchange requests so that I can manage my commitments.

Acceptance criteria:

- Incoming requests appear in a Requests inbox with sender's name, skill requested, and message.
- Accept and Decline buttons are present on each request; action triggers an in-app notification to sender.
- Declining a request moves it to declined history with an optional reason message.
- Accepting a request creates an exchange record and opens a messaging thread between both users.

#### US-13 / F4-4.3 - History Dashboard - Medium

As a user, I want a history dashboard so that I can track all my past and ongoing skill exchanges.

Acceptance criteria:

- Dashboard lists all exchanges with status: pending, active, completed, or declined; timestamps are visible.
- Completed exchanges show a `Leave a Review` button if no review has been submitted yet.
- User can filter history by status or date range to find specific exchanges quickly.
- Each history entry links to the original listing and the associated message thread.

#### US-14 / F4-4.4 - In-App Messaging - High

As a user, I want to send and receive in-app messages so that I can communicate with my exchange partners.

Acceptance criteria:

- Messaging interface shows a conversation list on the left and the active chat on the right.
- Messages support text up to 2000 characters; sent messages display a read or delivered indicator.
- Users can only message others they have an accepted exchange with or have been matched with.
- Messages are stored and retrievable; users can scroll up to view full conversation history.

#### US-15 / F4-4.5 - Unread Message Badge - Low

As a user, I want to see an unread message badge so that I know when I have new messages waiting.

Acceptance criteria:

- A numeric badge appears on the Messages icon in the navigation bar showing the count of unread messages.
- Badge count updates in real time or on page refresh without requiring a full page reload.
- Opening a conversation marks all messages in that thread as read and decrements the badge count.
- Badge disappears entirely when there are zero unread messages.

#### US-16 / F4-4.6 - In-App Notifications - Medium

As a user, I want to receive in-app notifications so that I stay informed about activity on my account.

Acceptance criteria:

- Notifications are generated for new match, exchange request, accepted or declined request, new message, and new review.
- Notifications panel is accessible from all pages through a bell icon in the navigation bar.
- Each notification shows a timestamp and a link to the relevant page or conversation.
- Users can mark notifications as read individually or use a `Mark all as read` option.

#### US-21 / F4-4.7 - Credit Ledger - Medium

As a user, I want a credit ledger system so that I can earn credits by teaching and spend them to learn.

Acceptance criteria:

- Users earn a configurable number of credits, default 10, upon successful completion of a teaching session.
- Requesting a skill from a one-sided listing deducts the required credits from the learner's balance.
- Ledger page shows a full transaction history with date, action, skill, and credit change for each entry.
- System prevents a user from initiating a credit-based request if their balance is insufficient.

#### US-29 / F4-4.8 - In-App Video Call - Low

As a user, I want to conduct a video call within the app so that I can have my skill exchange session seamlessly.

Acceptance criteria:

- A `Start Video Call` button appears in an active exchange's message thread; both parties must be online.
- Video call supports camera, microphone, and screen-sharing toggles with clear on/off indicators.
- Call ends for both participants when either party clicks `End Call`; a session summary is logged in the exchange record.
- If a participant's connection drops, they are prompted to rejoin within 2 minutes before the call is terminated.

### F5 - Administration

#### US-23 / F5-5.1 - Admin Dashboard - High

As an admin, I want an admin dashboard so that I can monitor platform activity and manage content.

Acceptance criteria:

- Dashboard displays summary metrics: total users, active listings, pending approvals, open reports, and daily exchanges.
- Admin can navigate to separate management sections: Users, Listings, Reports, and Reviews.
- All admin actions such as ban, approve, and reject are logged with timestamp and admin ID for audit purposes.
- Dashboard is only accessible to users with the `admin` role; regular users receive a 403 error.

#### US-24 / F5-5.2 - Listing Moderation - High

As an admin, I want to approve or reject skill listings so that only quality content appears on the platform.

Acceptance criteria:

- Pending listings queue shows new submissions with full details and approve or reject action buttons.
- Rejecting a listing requires entering a rejection reason; this reason is sent to the listing creator via notification.
- Approved listings become publicly visible within 5 minutes of approval.
- Admin can search and filter the pending queue by category, date submitted, or poster username.

#### US-25 / F5-5.3 - Ban or Suspend Users - High

As an admin, I want to ban or suspend users so that I can enforce community guidelines effectively.

Acceptance criteria:

- Admin can apply a temporary suspension from 1-30 days or a permanent ban from the user management panel.
- Banned or suspended users are immediately logged out and see a clear message explaining their account status.
- All active listings belonging to a banned user are automatically deactivated.
- Admin must enter a reason for the ban, which is stored in the audit log and optionally sent to the user.

#### US-26 / F5-5.4 - Role-Based Access Control - High

As an admin, I want role-based access control so that sensitive actions are protected based on user role.

Acceptance criteria:

- All admin routes return a 403 Forbidden response to any user without the `admin` role.
- Role is assigned at registration with default `user` and can only be elevated by an existing admin.
- Sensitive API endpoints validate the user's role on every request, not just on login.
- Frontend navigation hides admin-only links for regular users; backend enforces the same restrictions independently.

## 16. Sprint and Release Plan

The build plan must follow the release order below unless the team records a justified change.

| Sprint | Calendar Window | Release Date | Main Theme | Required Stories |
| --- | --- | --- | --- | --- |
| Sprint 1 | 2026-05-18 to 2026-05-22 | Internal foundation | Foundation | US-01, US-04, US-23, US-02, US-26, US-03 |
| Sprint 2 | 2026-05-25 to 2026-05-29 | 2026-05-31 | Listings foundation | US-05, US-06, US-24, US-07, US-08, US-09 |
| Sprint 3 | 2026-06-01 to 2026-06-05 | 2026-06-07 | Exchange coordination | US-17, US-10, US-11, US-12, US-14, US-16 |
| Sprint 4 | 2026-06-08 to 2026-06-12 | 2026-06-14 | Trust, history, credits | US-18, US-13, US-25, US-19, US-20, US-21 |
| Sprint 5 | 2026-06-15 to 2026-06-18 | 2026-06-21 | Final features and polish | US-27, US-22, US-30, US-15, US-28, US-29 |

The 13 week module timeline must also include research, design, final report writing, user guide writing, developer guide writing, testing, presentation preparation, and reflection. The five build sprints are not the entire module; they are the main implementation sequence.

## 17. Required Testing

Testing must prove both product behavior and technical quality.

Required automated tests:

- Registration validation and duplicate email rejection.
- Email verification token activation.
- Login success, login failure, lockout, and logout.
- Password hashing and password reset token expiry.
- Role-based access for admin pages.
- Listing creation, pending state, approval, rejection, search, and filtering.
- Request acceptance, decline, and exchange creation.
- Messaging permission rules.
- Credit balance checks and ledger entries.
- Review submission and reputation calculation.
- Report creation and duplicate report prevention.
- Account deletion or anonymization behavior.

Required manual browser tests:

- Full new-user journey: register, verify, profile setup, create listing.
- Learner journey: browse, search, filter, request, message, complete exchange, review.
- Teacher journey: receive request, accept or decline, message, complete exchange, receive credits.
- Admin journey: dashboard, approve listing, reject listing, handle report, suspend user.
- Responsive layout check on desktop and mobile widths.

Test evidence must include screenshots or short notes with date, story ID, expected result, actual result, and pass/fail status.

## 18. Required Documentation

The final submission must include:

- Product report explaining problem, aim, objectives, research, requirements, methodology, tools, architecture, ERD, workflow, scope, SWOT, testing, conclusion, and references.
- User guide explaining how normal users and admins use the platform.
- Developer guide explaining setup, config, database creation, folder structure, route registration, model/controller responsibilities, and test execution.
- Sprint evidence such as Trello board screenshots, Gantt chart, sprint backlog, sprint reviews, sprint retrospectives, and GitHub history.
- LESPI section covering privacy, informed consent, moderation, safety, accessibility, fairness, data deletion, and ethical use of ratings.
- Risk assessment covering technical risk, team risk, schedule risk, database risk, credit logic risk, and moderation risk.

## 19. Presentation Rules

The final demo must show the credit cycle clearly:

1. A user registers and logs in.
2. The user creates or edits a profile.
3. The user posts a skill.
4. Admin approves the skill.
5. Another user searches and requests the skill.
6. Teacher accepts.
7. Messaging opens.
8. Session is completed.
9. Credits move from learner to teacher.
10. Review is submitted.
11. Reputation updates.
12. Admin dashboard shows platform activity.

The team must be ready to explain:

- Why the project uses credits instead of money.
- How the database protects consistency.
- How password and role security work.
- How the team used Agile.
- How LESPI concerns were handled.
- What is included, what is excluded, and why.

## 20. Implementation Quality Rules

The project must remain small enough for a Level 4 team but complete enough to show integration across programming, databases, systems, and professional practice.

Build order must be:

1. Authentication, roles, and profile foundation.
2. Admin dashboard and role access.
3. Skill listings and approval.
4. Search, category filtering, and listing detail pages.
5. Requests and exchange records.
6. Messaging and notifications.
7. Credit ledger.
8. Reviews and reputation.
9. Reporting and moderation.
10. Account deletion, certificate upload, top-rated users, location filter, unread badge, and video call.
11. Testing, documentation, and polish.

No feature is complete until it has working UI, controller logic, model/database behavior, validation, access control, and test evidence.
