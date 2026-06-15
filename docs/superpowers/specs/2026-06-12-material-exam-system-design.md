# Project Material Exam System Design

## Goal

Build a responsive web-based exam system for project material management training. The first version runs locally for demonstration, but the architecture should be ready to move to a server later.

The system will use the provided Word document in the project root as the initial question source. The importer should discover the `.docx` file from the working directory instead of depending on a hard-coded Chinese filename.

## Users And Roles

### Employee

Employees are distributed across different regions and projects. They register themselves, then wait for administrator approval.

Registration fields:

- Name
- Mobile number
- Password
- Region or branch company
- Project department
- Job position

Approved employees can practice, take exams, and view their own results.

### Administrator

Administrators can approve users, manage imported papers and questions, review subjective answers, query results, and export result data.

The first version should include one built-in administrator account so the system is usable immediately after startup.

## Scope

### Included

- Responsive web UI for desktop and mobile.
- Employee self-registration.
- Administrator review and approval.
- Login with role-based views.
- Import or seed the 5 papers from the provided Word document.
- Practice mode.
- Timed exam mode.
- Objective auto-grading.
- Subjective keyword-based suggested scoring.
- Administrator subjective answer review and score adjustment.
- Personal result lookup.
- Administrator result query and CSV export.
- SQLite persistence for local demo use.

### Not Included In First Version

- SMS verification.
- Enterprise SSO.
- Payment or external integrations.
- Advanced anti-cheating proctoring.
- Multi-tenant isolation beyond organization fields.
- Production deployment automation.

## Architecture

Use a lightweight full-stack app:

- Frontend: responsive single-page web UI.
- Backend: API service for accounts, papers, exams, grading, and admin operations.
- Database: SQLite for local persistence.
- Data import: parse the provided Word document into structured papers, questions, options, answers, scores, and reference answers.

The backend should keep domain boundaries clear:

- User and approval module.
- Question bank and paper module.
- Practice and exam module.
- Grading module.
- Result query and export module.

This keeps the first version simple while leaving room to replace SQLite with MySQL or PostgreSQL later.

## Question And Paper Model

The source Word document contains 5 independent papers. Each paper follows the same score model:

- Single choice: 16 questions, 2 points each, 32 points total.
- Multiple choice: 10 questions, 3 points each, 30 points total.
- True or false: 9 questions, 1 point each, 9 points total.
- Short answer: 2 questions, 7 points each, 14 points total.
- Case analysis: 1 case, 15 points total.
- Exam duration: 50 minutes.
- Full score: 100 points.

Question types:

- `single_choice`
- `multiple_choice`
- `true_false`
- `short_answer`
- `case_analysis`

Each question stores:

- Paper id.
- Type.
- Order number.
- Stem.
- Options, when applicable.
- Correct answer, when objective.
- Reference answer, when subjective.
- Score.
- Keywords for suggested subjective scoring.

## Employee Flow

### Registration

The employee submits registration information. The account starts in `pending` status.

Pending users can log in only to see their review status. They cannot practice or take exams.

### Home

Approved users see:

- Available practice papers.
- Available exams.
- Recent exam result summary.
- Current review or scoring reminders, if any.

### Practice Mode

Practice mode is for learning. It can show questions by paper and type.

After answering, the user can see:

- Their answer.
- Correct answer for objective questions.
- Reference answer for subjective questions.
- Score feedback where applicable.

Practice attempts do not count as official exam results.

### Exam Mode

Exam mode uses the selected paper and a 50-minute countdown.

Expected behavior:

- Save answers during the exam.
- Warn before leaving when possible.
- Auto-submit when time expires.
- Submit manually when the user finishes.
- Grade objective questions immediately.
- Mark subjective questions as pending administrator review.

After submission, the employee sees:

- Objective score.
- Subjective suggested score, if available.
- Final score status: pending review or completed.

### My Results

Employees can view their own exam attempts:

- Paper name.
- Submit time.
- Objective score.
- Suggested subjective score.
- Final subjective score.
- Final total score.
- Review status.

## Administrator Flow

### User Approval

Administrators can filter users by:

- Region or branch company.
- Project department.
- Job position.
- Status.
- Name or mobile number.

Actions:

- Approve.
- Reject.
- View registration details.

### Question Bank

Administrators can view the imported 5 papers.

For each question, administrators can edit:

- Stem.
- Options.
- Correct answer.
- Reference answer.
- Score.
- Keywords used for suggested subjective scoring.

### Subjective Review

Administrators review short answer and case analysis responses.

The review screen shows:

- Paper and question.
- Candidate information.
- Candidate answer.
- Reference answer.
- Keyword hit details.
- Suggested score.
- Editable final score.

Once all subjective questions in an exam attempt are reviewed, the final score is locked as completed.

### Result Query

Administrators can filter by:

- Region or branch company.
- Project department.
- Job position.
- Name or mobile number.
- Paper.
- Date range.
- Review status.

The result list shows:

- Candidate identity and organization.
- Paper name.
- Submit time.
- Objective score.
- Subjective suggested score.
- Final score.
- Review status.

Administrators can export the filtered result list as CSV.

### Dashboard

The admin dashboard shows:

- Total registered users.
- Pending users.
- Approved users.
- Exam participants.
- Average score.
- Pending reviews.
- Users who have not completed an exam.

## Scoring Rules

### Objective Questions

Single choice and true or false:

- Exact match gets full score.
- Otherwise gets 0.

Multiple choice:

- Exact option set match gets full score.
- More choices, fewer choices, and wrong choices all get 0.

### Subjective Questions

The system generates a suggested score using keyword matching:

- Extract keywords or key phrases from the reference answer during import.
- Allow administrators to edit keywords.
- Compare candidate answer with keywords.
- Calculate suggested score by keyword hit ratio, capped by the question score.

The suggested score is not final. Administrators can accept or adjust it.

The official final score is:

- Objective score plus administrator-confirmed subjective score.

Before subjective review is completed, the attempt status is `pending_review`.

## Responsive UI

Desktop layout:

- Left or top navigation depending on screen width.
- Dense tables for admin query screens.
- Main content area optimized for repeated review and filtering.

Mobile layout:

- Bottom navigation for employee views: Home, Practice, Exam, Results, Profile.
- Admin tables become filterable card lists.
- Exam questions use large tap targets and stable question spacing.
- Long subjective answers use full-width text areas.

The interface should be practical and work-focused, not a marketing landing page.

## Data Persistence

Use SQLite in the first version.

Core tables:

- users
- papers
- questions
- question_options
- exam_attempts
- answers
- subjective_reviews
- practice_attempts

Data must survive service restart.

## Error Handling

- Registration validates required fields and duplicate mobile numbers.
- Login rejects pending or rejected users from exam functions.
- Exam submission handles missing answers.
- Auto-submit should submit the latest saved answers when possible.
- Admin scoring validates that subjective score is within the question score.
- Import failures should report which paper or question could not be parsed.

## Verification Criteria

The first implementation is acceptable when:

- The system starts locally with one command or a short documented command sequence.
- The Word document is parsed or its content is seeded into the database.
- An employee can register and wait for approval.
- An administrator can approve the employee.
- The approved employee can practice.
- The approved employee can complete a timed exam.
- Objective questions are graded correctly.
- Subjective answers receive suggested scores.
- An administrator can review and finalize subjective scores.
- The employee can see the finalized result.
- The administrator can filter and export results.
- Desktop and mobile widths are usable without broken layout or overlapping text.

## Open Constraints

The project directory is not currently a git repository, so the design document cannot be committed unless a repository is initialized later.
