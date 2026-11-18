# Product Requirements Document

## Student Skill & Project Team Finder

> A student-started platform for forming project teams through complementary skills, availability and shared interests.

| **Document version**     | 1.0 - Draft                                                   |
|--------------------------|---------------------------------------------------------------|
| **Prepared on**          | 17 November 2026                                              |
| **Context**              | Innovation & Design Thinking Project                          |
| **Institution / cohort** | BMS Institute of Technology and Management (BMSIT&M) - CSE 13 |

> Prepared from the supplied 14-slide IDT presentation. Source facts and missing evidence are called out explicitly; proposed product and engineering decisions are labelled as recommendations.

> **Product thesis**  
> Let students describe the skills a project needs, then surface classmates whose skills, availability and interests fit. The product should make skill coverage visible before a team is finalized.

**Team:** Harsh Tiwari, Benaka Sham, Goral Chhabra and Akansha.

---

# 1. Executive Summary

What is being built and why.

Student Skill & Project Team Finder is a proposed web application for college students who need teammates for course projects. A student creates a profile with skills, interests and availability. A project owner posts the project requirements. The system ranks potential teammates, explains the fit and lets the project owner invite students and form a team.

The core product distinction in the presentation is requirement-first and student-started matching. It is intended to improve on teams formed only through friendship, where a team may have several coders but lack UI/UX, database, testing or presentation capability.

> **PRD recommendation**  
> Build a narrow MVP around the complete team-formation loop: create a student profile → publish a project and required skills → view explainable matches → send/accept invitations → see team skill coverage. Do not start with AI, peer ratings, mobile push notifications or complex automatic team assignment.

| **At a glance**  | **Definition**                                                                                                             |
|------------------|----------------------------------------------------------------------------------------------------------------------------|
| Primary users    | Students forming teams for college course projects; begin with first-year CSE students, as stated in the deck.             |
| Secondary users  | Teachers, mentors, club coordinators and hackathon coordinators; advanced review tools are not required for the first MVP. |
| Core value       | Make complementary skills, project requirements and availability visible before students commit to a team.                 |
| MVP platform     | Responsive web application; mobile-friendly browser experience is sufficient for the first release.                        |
| Current maturity | Concept and problem-discovery stage. Demand, baseline pain and matching weights still need validation.                     |

# 2. Data Analyst Review of the Presentation

Source-based findings, evidence quality and what the data can support.

## 2.1 What the deck establishes

- The problem selected is specific: project teams may form around friendship rather than the skills a project requires.

- The proposed user groups are clear: students are primary; teachers/mentors and club or hackathon coordinators are secondary.

- The proposed workflow is coherent: student profile, project requirements, match ranking and connection/invitation.

- The presentation identifies plausible root causes across people, process, management, technology, information and environment.

- The proposed differentiator is student-started, requirement-first matching for course projects.

## 2.2 Evidence inventory and data-quality assessment

| **Evidence item in deck**  | **What is reported**                                                     | **Analyst assessment**                                                                                           |
|----------------------------|--------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------|
| Classmate survey           | Survey of 20 classmates; three result fields are shown as “\_\_ / 20”.   | Sample size is stated, but outcome counts are missing. No percentages or conclusions can be computed.            |
| Friend-only team formation | A survey question asks how the last team was formed.                     | The problem hypothesis is plausible, but prevalence is not measured in the supplied deck.                        |
| Missing team skill         | A survey question asks whether a key skill was missing.                  | No count, skill breakdown or project context is reported.                                                        |
| Adoption interest          | A question asks whether respondents would use a skill-based team finder. | No count is reported. Stated intent is not the same as actual use.                                               |
| Short interviews           | The methods include short interviews.                                    | Number of interviewees, notes, themes and quotes are not included.                                               |
| Observation                | Observation is listed as a method.                                       | No observation protocol or findings are presented.                                                               |
| Uneven workload            | The deck states that one or two members may do most of the work.         | No workload distribution measure or respondent count is included.                                                |
| Existing solutions         | CATME, Teamable, hackathon finders and informal channels are compared.   | Useful landscape framing; current capability claims and citations should be checked before external publication. |
| CATME scale                | 2M+ students, 93 countries and 2,600+ institutions are cited.            | Treat as presentation-reported figures; confirm the original source and date before reusing.                     |
| 2026 research paper        | A database-driven matching paper is mentioned as article 04011.          | Full bibliographic details and study limitations are not provided in the slide.                                  |

> **Data integrity warning**  
> Do not replace the blank survey figures with illustrative numbers. The three KPI placeholders are unresolved source data, not zeroes. Keep them blank until the original survey responses are counted and checked.

## 2.3 What can and cannot be concluded

| **Can be concluded from the deck**                                                                               | **Cannot yet be concluded**                                                                               |
|------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| The team has identified a concrete user problem and a testable solution concept.                                 | That most students form teams only with friends, or that a majority experience skill gaps.                |
| The initial target context is college course projects, starting with first-year CSE.                             | How often skill gaps occur, which skills are most often missing, or how much time is lost.                |
| Students should be able to describe skills, interests and availability; projects should declare required skills. | That students will actively maintain profiles, trust self-reported skills, or use the product repeatedly. |
| A ranking signal combining skills, availability and interests is part of the concept.                            | The correct score weights, ranking threshold, team size or availability granularity.                      |
| Privacy and consent are recognized as design concerns in the deck.                                               | That the proposed product is legally compliant; this requires a separate institutional/privacy review.    |

## 2.4 Survey analysis to complete before claiming validation

Reopen the original 20 response records, remove duplicates, check missing answers and calculate each metric using the number of valid responses for that question as its denominator. Do not automatically use 20 as every denominator if some answers are blank.

| **Metric**                                       | **Calculation**                                                                | **Required source field**                  |
|--------------------------------------------------|--------------------------------------------------------------------------------|--------------------------------------------|
| Friend-first team formation                      | Count selecting “friends only” ÷ valid answers to team-formation question.     | Team formation method                      |
| Missing-skill incidence                          | Count reporting a missing key skill ÷ valid answers to missing-skill question. | Missing key skill: yes/no; skill type      |
| Stated adoption interest                         | Count answering “yes” ÷ valid answers to willingness question.                 | Would use skill-based tool: yes/no/unsure  |
| Uneven-workload incidence (recommended addition) | Count reporting one/two members did most of the work ÷ valid answers.          | Workload distribution / perceived fairness |
| Most requested skills (recommended addition)     | Frequency by skill category, using multiple-response counts.                   | Missing or hard-to-find skills             |

Interpretation caution: a convenience sample of 20 classmates is useful for early discovery, but it is not representative evidence for the whole college. Present results as “among the 20 classmates surveyed” and avoid campus-wide claims.

# 3. Product Definition

Problem, users, goals and scope.

## 3.1 Problem statement

> **Problem statement**  
> College students forming project teams often rely on existing friend circles. This can leave project-critical skills uncovered and create uneven contribution. Students need a simple way to state project skill requirements and discover classmates whose skills, availability and interests complement the team.

## 3.2 User personas

| **Persona**                          | **Need / pain point**                                                            | **MVP outcome**                                                                                                                     |
|--------------------------------------|----------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| Project owner / team seeker          | Has a project idea or assignment and needs teammates with specific capabilities. | Posts required skills and schedule; compares matches; invites suitable students.                                                    |
| Student with under-recognized skills | Has skills outside their immediate friend group but is not easily discovered.    | Creates a searchable profile and receives relevant project invitations.                                                             |
| Teacher / mentor / coordinator       | Wants teams to be balanced and collaboration to be fair.                         | For MVP, can review aggregate usage or reported concerns only if an admin view is explicitly approved; full oversight can be later. |

## 3.3 Product goals

- Help a student find teammates who cover the project’s required skills.

- Make availability and shared interests visible during discovery.

- Make matching explainable: show which requested skills a candidate covers and where gaps remain.

- Make invitations and team formation explicit, with clear pending/accepted/declined states.

- Help students discover talent beyond their immediate friend circle.

## 3.4 Non-goals for the first MVP

- AI-generated assessment of student ability or automated grading of portfolios.

- Automatic forced team assignment by teachers.

- Peer ratings, reputation scores or public leaderboards.

- Native Android/iOS apps and push notifications.

- Payments, recruitment, internships or a general social network.

- Cross-college matching; the pilot starts within the approved BMSIT&M student cohort.

# 4. Core User Journeys

Primary end-to-end flows for the MVP.

| **Journey**          | **Steps**                                                                                                                                           | **Success state**                                                        |
|----------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| Student onboarding   | Sign in / register → provide basic academic identity → add skills and proficiency → choose interests → enter availability → set profile visibility. | Profile is complete enough to be considered in project matches.          |
| Create a project     | Create project → add title/description/course or context → set team size and expected schedule → add required skills and priority → publish.        | Project is discoverable and has at least one required skill.             |
| Discover matches     | Open project → view ranked students → review skill, availability and interest fit → apply filters → open profile summary.                           | Project owner can understand why a student is recommended.               |
| Invite and accept    | Send invitation → invited student receives in-app notification → accept or decline → owner sees updated status.                                     | Team membership changes only after explicit acceptance.                  |
| Review team coverage | View accepted members and required skill coverage → identify remaining gaps → invite additional members or close project.                           | Team owner can see covered and uncovered requirements before finalizing. |

# 5. Functional Requirements

Prioritized requirements and testable acceptance criteria.

Priority definitions: P0 = required for a usable MVP; P1 = valuable after the core loop works; P2 = future enhancement. Acceptance criteria below are proposed engineering checks.

| **ID** | **Requirement**                  | **Priority** | **Acceptance criteria**                                                                                                                                    |
|--------|----------------------------------|--------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| FR-01  | Student registration and sign-in | P0           | A student can create an account and sign in. Invalid credentials are rejected. The pilot can restrict access to an approved institution or cohort.         |
| FR-02  | Student profile                  | P0           | A student can create and edit basic profile details. Required profile fields are validated before the profile is marked match-ready.                       |
| FR-03  | Skills and proficiency           | P0           | A student can add skills from a controlled skill list and select a self-reported proficiency level. The UI labels skills as self-reported unless verified. |
| FR-04  | Interests and availability       | P0           | A student can select interest tags and weekly availability blocks. The student can update these later.                                                     |
| FR-05  | Create and publish project       | P0           | A project owner can create, edit, publish, close and archive a project. Draft projects are not included in discovery.                                      |
| FR-06  | Project skill requirements       | P0           | A project owner can add one or more required skills and mark each as must-have or preferred. Empty requirements cannot be published.                       |
| FR-07  | Ranked candidate suggestions     | P0           | For an open project, the system returns eligible students ordered by the configured match score. The ranking is deterministic for the same input data.     |
| FR-08  | Match explanation                | P0           | Each suggestion shows matched skills, missing requirements, availability overlap and shared interests. A single opaque score is not the only explanation.  |
| FR-09  | Search and filters               | P1           | The owner can filter suggestions by skill, year/section (where permitted), availability and interest. Filters do not reveal hidden profile fields.         |
| FR-10  | Invitations                      | P0           | A project owner can invite a candidate. The candidate can accept or decline. Duplicate active invitations are prevented.                                   |
| FR-11  | Team roster and coverage         | P0           | The project page lists accepted members, pending invitations and remaining skill gaps. Membership is updated only after acceptance.                        |
| FR-12  | Profile privacy controls         | P0           | A student can choose which profile fields are visible to other students and can deactivate their profile.                                                  |
| FR-13  | Basic reporting / moderation     | P1           | A user can report an inappropriate profile or project. An authorized administrator can review and resolve reports.                                         |
| FR-14  | Portfolio links                  | P2           | A student can optionally attach external portfolio links such as GitHub. Links are optional and not treated as proof without verification.                 |
| FR-15  | Notifications / match alerts     | P2           | The system can send configurable email or mobile alerts for invitations and relevant matches.                                                              |

# 6. Matching Logic

Engineering proposal: explainable, requirement-first ranking.

The presentation defines the conceptual score as “skills covered + availability overlap + shared interests” but does not specify a mathematical formula, normalization method or weights. The following is a proposed starting model for a pilot and must be calibrated with real student feedback.

> **Proposed v1 candidate score**  
> Match Score = 0.65 × Skill Fit + 0.25 × Availability Fit + 0.10 × Interest Fit. Each component is normalized to 0–100, producing a final score from 0–100. Store the component scores so the interface can explain the recommendation.

## 6.1 Component definitions

| **Component**          | **Proposed calculation**                                                                                                                                                                                | **Reason**                                                                              |
|------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| Skill Fit (65%)        | Sum of weights for project-required skills the student reports having ÷ total weights of all required skills × 100. A must-have skill may carry a higher project-defined weight than a preferred skill. | Skills are the primary differentiator in the project concept.                           |
| Availability Fit (25%) | Overlapping available time blocks ÷ project-required time blocks × 100. If project schedule is not known, show “not enough availability data” rather than treating it as 100%.                          | A student with matching skills still needs time to contribute.                          |
| Interest Fit (10%)     | Shared project/student interest tags ÷ project interest tags × 100, with a clear “no tags provided” state.                                                                                              | Interest is a tie-breaker / compatibility signal, not a substitute for required skills. |

## 6.2 Ranking safeguards

- Show must-have skill gaps separately; do not let high interest or availability hide a critical skill gap.

- Keep self-reported proficiency distinct from verified competence. Do not present the score as an objective measure of talent.

- If a component is missing, label it as unavailable and document how the score is normalized; do not silently award a perfect score.

- Apply eligibility rules before ranking: active profile, project open, invitation eligibility and any cohort restrictions approved for the pilot.

- Prevent the same student from being counted twice in a project team. Enforce team-size limits.

- As a team grows, display team-level skill coverage so the owner can avoid inviting only candidates with already-covered skills.

## 6.3 Worked example (illustrative only)

A project requires Python (weight 3), UI/UX (weight 2) and presentation (weight 1). A candidate reports Python and presentation, has 80% availability overlap and 50% interest overlap. Skill fit = (3 + 1) / (3 + 2 + 1) = 66.7. Proposed score = 0.65×66.7 + 0.25×80 + 0.10×50 = 68.3/100. The UI should also state “UI/UX requirement not covered”; this explanation is more useful than the score alone. This example is not survey data.

# 7. Data and System Design

Suggested minimum architecture and core entities.

## 7.1 Suggested logical data model

| **Entity**                    | **Key fields / relationships**                                                                                 |
|-------------------------------|----------------------------------------------------------------------------------------------------------------|
| User                          | user_id, institutional_email, password_hash / identity_provider_id, account_status, created_at                 |
| StudentProfile                | user_id, display_name, branch, year, section, bio, visibility_settings, profile_status                         |
| Skill                         | skill_id, skill_name, category, active_flag                                                                    |
| StudentSkill                  | user_id, skill_id, proficiency_level, self_reported_flag, updated_at                                           |
| InterestTag / StudentInterest | tag_id, tag_name; user_id, tag_id                                                                              |
| AvailabilitySlot              | slot_id, user_id, day_of_week, start_time, end_time, timezone                                                  |
| Project                       | project_id, owner_user_id, title, description, course_context, team_size_min/max, schedule, status, created_at |
| ProjectSkillRequirement       | project_id, skill_id, priority, weight, required_count                                                         |
| MatchSnapshot                 | project_id, candidate_user_id, skill_fit, availability_fit, interest_fit, total_score, generated_at            |
| Invitation                    | invitation_id, project_id, inviter_user_id, invitee_user_id, status, created_at, responded_at                  |
| TeamMember                    | project_id, user_id, role, membership_status, joined_at                                                        |
| Report / AuditEvent           | report_id or event_id, actor_id, target_type, target_id, action, status, timestamp                             |

Use stable IDs and relational constraints for project membership and invitations. A relational database is a natural fit because profiles, skills, projects, requirements, invitations and memberships are connected records.

## 7.2 Suggested API surface

| **Method / endpoint**                                    | **Purpose**                                                     |
|----------------------------------------------------------|-----------------------------------------------------------------|
| POST /auth/register; POST /auth/login                    | Create account and establish a session.                         |
| GET /me; PATCH /me/profile                               | Retrieve and update the signed-in student profile.              |
| PUT /me/skills; PUT /me/availability                     | Replace or update skill and availability selections.            |
| POST /projects; GET /projects/{id}; PATCH /projects/{id} | Create, view and update a project.                              |
| PUT /projects/{id}/requirements                          | Set the required skill list and priorities.                     |
| GET /projects/{id}/matches                               | Return ranked candidates with score components and explanation. |
| POST /projects/{id}/invitations                          | Invite a candidate.                                             |
| PATCH /invitations/{id}                                  | Accept or decline an invitation.                                |
| GET /projects/{id}/team                                  | Return roster, invitation status and skill coverage.            |

## 7.3 Architecture recommendation

Keep the first release as a responsive web application with three logical layers: browser UI, application/API layer and relational database. The matching calculation can initially run in the application layer; a separate recommendation service is unnecessary for a small campus pilot. Add caching or background jobs only if measured performance requires them.

Implementation stack is an engineering choice, not specified by the presentation. A beginner-friendly prototype could use HTML/CSS/JavaScript, a Python Flask API and SQLite. If multiple teams/classes will use it concurrently, consider a managed relational database such as PostgreSQL. Choose after checking the team’s skill, hosting constraints and institutional policy.

# 8. Non-Functional Requirements

Quality, privacy, security and operational expectations.

| **Area**                     | **Requirement / recommendation**                                                                                                                                                                          |
|------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Usability                    | A student should be able to complete a basic profile and publish a project without training. Use plain labels, skill examples and clear empty states.                                                     |
| Responsive design            | Core flows must work on common mobile and laptop screen sizes. A native app is not required for the pilot.                                                                                                |
| Performance                  | Proposed pilot target: common pages load within 2 seconds and a match list for the pilot cohort returns within 3 seconds under normal college network conditions. Measure before tightening targets.      |
| Security                     | Use HTTPS in deployment, secure password hashing or a trusted identity provider, server-side authorization, input validation and rate limits for sign-in/invitations.                                     |
| Privacy                      | Collect only fields required for matching. Give students clear notice and consent; make sensitive contact details non-public by default; allow profile deactivation and a data deletion/request workflow. |
| Access control               | A student may edit their own profile and projects they own. Invitees may respond only to their own invitations. Administrative access must be restricted and logged.                                      |
| Reliability                  | Back up the database regularly during the pilot and test restore. Handle duplicate invitations, expired projects and partial failures safely.                                                             |
| Accessibility                | Use keyboard-accessible controls, visible focus, readable contrast, form labels and text alternatives for status indicators.                                                                              |
| Transparency                 | Explain that skills and proficiency are self-reported unless verification is implemented. Avoid presenting match scores as guarantees of performance.                                                     |
| Legal / institutional review | The presentation references the DPDP Act 2023 and consent. Before collecting real student data, obtain institutional review of the applicable privacy notice, consent, retention and grievance process.   |

# 9. Product Analytics and Success Metrics

Measure whether the product improves team formation, not just whether users sign up.

> **North Star Metric - proposed**  
> Percentage of projects that reach their target team size while covering all must-have skills before the project deadline. This combines team formation and the product’s central skill-coverage promise.

| **Metric**                  | **Definition**                                                                         | **Instrumentation / notes**                                                  |
|-----------------------------|----------------------------------------------------------------------------------------|------------------------------------------------------------------------------|
| Profile completion rate     | Match-ready student profiles ÷ registered student accounts.                            | profile_completed; define mandatory profile fields.                          |
| Project publish rate        | Published projects ÷ project drafts created.                                           | project_created, project_published; track validation failures.               |
| Must-have skill coverage    | Required must-have skills represented by accepted team members ÷ all must-have skills. | Calculate at project/team level; record coverage snapshots over time.        |
| Match-to-invitation rate    | Candidates invited ÷ candidates viewed in match results.                               | match_list_viewed, candidate_viewed, invitation_sent.                        |
| Invitation acceptance rate  | Accepted invitations ÷ invitations with a final response.                              | invitation_accepted, invitation_declined; exclude pending from denominator.  |
| Time to form a team         | Time from project publication to target team size being reached.                       | Capture project_published_at and team_target_reached_at.                     |
| Repeat usage                | Students who create/join another project within a defined period.                      | Use only after the pilot has enough time and users.                          |
| Perceived workload fairness | Post-project self-rating of contribution balance.                                      | Optional post-project survey; do not infer fairness only from matching data. |

Do not set campus-wide targets before collecting a baseline. Establish a baseline in the pilot, agree targets with the course team, then compare results by cohort and project type. Report counts and denominators alongside percentages, especially for small samples.

## 9.1 Minimum event tracking

Track: account_created, profile_completed, skills_updated, availability_updated, project_created, project_published, match_list_viewed, candidate_profile_viewed, invitation_sent, invitation_accepted, invitation_declined, team_target_reached, project_closed, report_submitted. Store event time and relevant IDs; avoid logging passwords, private messages or unnecessary personal data.

# 10. Validation and QA Plan

What to test before a classroom pilot.

| **Test area**           | **Test cases / evidence required**                                                                                                                     | **Exit condition**                                                                |
|-------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------|
| Usability               | Ask first-year students to complete profile, create project, find a candidate and send an invite without coaching. Observe confusion and time on task. | Core tasks can be completed without facilitator intervention; blockers are fixed. |
| Matching correctness    | Test exact skill match, partial skill match, no skill match, different availability, missing interest tags and equal-score candidates.                 | Scores and explanations are deterministic and agree with documented rules.        |
| Team coverage           | Invite candidates with overlapping skills and candidates who fill a missing skill.                                                                     | Coverage view correctly updates as invitations are accepted.                      |
| Invitation lifecycle    | Accept, decline, duplicate invite, invite after project closed, candidate already at capacity.                                                         | No duplicate or invalid memberships; states are consistent across screens.        |
| Privacy and permissions | Try to edit another user’s profile, view private fields, respond to another user’s invite and access closed project data.                              | Unauthorized requests are rejected server-side.                                   |
| Data quality            | Missing skills, invalid time blocks, duplicate accounts, malformed links and empty project requirements.                                               | Validation prevents unusable records and explains how to correct them.            |
| Pilot usefulness        | Collect post-task feedback: relevance, trust, fairness, missing filters and whether a team was successfully formed.                                    | Use findings to revise weights, onboarding and scope before broader release.      |

# 11. MVP Delivery Plan

A staged route from prototype to pilot.

| **Stage**                     | **Build / activity**                                                                                                                           | **Deliverable / gate**                                                        |
|-------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| Stage 0 - validate            | Complete the original 20-person survey analysis; run a few short interviews; define allowed profile fields and project workflow with a mentor. | Validated problem summary, baseline metrics, agreed scope and privacy review. |
| Stage 1 - clickable prototype | Design onboarding, profile, create project, match results, candidate detail and invite states. Test with classmates.                           | Usability-tested flow and revised screen designs.                             |
| Stage 2 - functional MVP      | Implement sign-in, profile, skills, availability, project requirements, scoring, invitations and team coverage.                                | End-to-end working web application.                                           |
| Stage 3 - controlled pilot    | Run with one defined cohort / course project set. Collect product events and feedback.                                                         | Pilot dashboard, issue log, user feedback and updated scoring recommendation. |
| Stage 4 - iterate             | Tune weights; decide whether to add filters, moderation, portfolio links or alerts based on evidence.                                          | Prioritized v1.1 backlog based on measured needs.                             |

# 12. Risks, Dependencies and Mitigations

The most important product and engineering risks.

| **Risk / dependency**              | **Why it matters**                                                 | **Mitigation**                                                                                                 |
|------------------------------------|--------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------|
| Low or incomplete profile adoption | Sparse skills and availability make recommendations weak.          | Keep onboarding short; show the benefit; allow later edits; measure match-ready profiles.                      |
| Self-reported skill accuracy       | A score could create false confidence in a candidate’s ability.    | Label self-reported data; use optional evidence links later; do not claim verification.                        |
| Cold start                         | Early projects may have too few students to match.                 | Launch to a bounded cohort; allow invite-by-link or interest registration; show “not enough matches” honestly. |
| Unclear project requirements       | Project owners may not know which skills they need.                | Provide a curated skill taxonomy and example requirement templates; allow editing.                             |
| Ranking bias / unfairness          | Students with polished profiles or more visibility may be favored. | Make criteria transparent; avoid popularity ranking; monitor who receives and accepts invitations.             |
| Privacy / consent                  | Student profiles and schedule data can be sensitive.               | Minimize data, restrict visibility, obtain institutional approval and provide deactivation/deletion path.      |
| Unverified external product claims | Competitor and CATME statistics may be challenged.                 | Retain source URLs and access dates in the final academic submission; verify before presenting claims.         |

# 13. Open Decisions Before Development

Decisions that cannot be resolved from the presentation alone.

| **Decision**                                      | **Recommended default for pilot**                                                                                    | **Owner / sign-off**           |
|---------------------------------------------------|----------------------------------------------------------------------------------------------------------------------|--------------------------------|
| Who can register?                                 | Students in the approved BMSIT&M pilot cohort; decide institutional email or roster-based verification.              | Project team + faculty mentor  |
| Can students join multiple projects?              | Allow multiple only when schedules do not conflict; define maximum active commitments.                               | Project team + course owner    |
| Who owns a project?                               | One student owner, with optional co-owner added later.                                                               | Product team                   |
| What is the team-size rule?                       | Owner selects minimum and maximum team size at project creation.                                                     | Course / faculty mentor        |
| How detailed is availability?                     | Weekly day/time blocks for MVP; avoid calendar integration.                                                          | Product team                   |
| Are skill levels mandatory?                       | Use beginner / intermediate / advanced, clearly labelled self-reported.                                              | Product team                   |
| Can other students see names and contact details? | Show only approved profile fields; reveal direct contact only after invitation acceptance or explicit opt-in.        | Institution / privacy reviewer |
| Will teachers approve projects or view matches?   | Not in core MVP unless a course requires it.                                                                         | Faculty mentor                 |
| What counts as a successful team?                 | Target size reached and all must-have skills covered; define exception handling.                                     | Project team + course owner    |
| What privacy process applies?                     | Confirm applicable notice, consent, retention and request handling with the institution before real data collection. | Institution / privacy reviewer |

# 14. Final Product Recommendation

What the team should build first.

The presentation is a good starting point for an IDT concept: it identifies a recognizable teamwork problem, describes primary users, compares existing approaches and proposes a focused differentiator. Its main weakness is evidence completeness. The survey is described but its three headline counts are blank, and the qualitative research is not summarized. Therefore, the deck supports moving into prototype validation, not claiming that demand or impact has already been proven.

For engineering, avoid building a broad “AI team finder.” Build the smallest system that tests the central hypothesis: when students can describe project requirements and student skills/availability are visible, can they form more complete teams with less effort? The MVP should show transparent skill coverage and give control to students through invitations and explicit acceptance.

> **Go / no-go recommendation**  
> Proceed with a clickable prototype and complete the missing research data before full implementation. Start functional development only after the team agrees the pilot cohort, required profile fields, project/team rules, visibility settings and privacy approval.

# Appendix A. Improved Discovery Survey

A short instrument to complete the evidence missing from the presentation.

| **Question**                                                                | **Suggested response format**                                                                          | **Analysis use**                                       |
|-----------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------|--------------------------------------------------------|
| How did you form your most recent project team?                             | Friends / assigned by teacher / skill-based search / other.                                            | Friend-first formation rate.                           |
| Did the team lack any skill needed to complete the project?                 | Yes / No; if yes, choose skill(s).                                                                     | Skill-gap rate and most frequently missing skills.     |
| How evenly was work distributed?                                            | 5-point scale from “very uneven” to “very even”.                                                       | Workload fairness baseline.                            |
| How long did it take to form the team?                                      | Same day / 1–3 days / 4–7 days / more than a week.                                                     | Time-to-team baseline.                                 |
| Would you try a tool that suggests teammates based on project requirements? | Definitely / probably / unsure / probably not / definitely not.                                        | Stated interest; keep separate from actual activation. |
| What would make you trust a suggested teammate?                             | Select all: demonstrated work / portfolio / mutual course / availability / mentor endorsement / other. | Trust requirements and roadmap priorities.             |

Sampling note: retain anonymous respondent IDs, record the cohort/context, report valid n for each question, and do not collect personal identifiers unless they are necessary and approved. Include a “prefer not to answer” option where appropriate.

# Appendix B. Source-to-PRD Traceability

How major PRD decisions map back to the presentation.

| **Presentation content**                                               | **PRD location / treatment**                                          |
|------------------------------------------------------------------------|-----------------------------------------------------------------------|
| Slides 2–3: concept and skill-gap problem                              | Sections 1 and 3; problem statement and product thesis.               |
| Slide 4: students, teachers and coordinators                           | Section 3.2; personas and MVP audience.                               |
| Slide 5: survey of 20, blank KPI placeholders                          | Section 2; evidence gap and calculations required.                    |
| Slide 6: fishbone root causes                                          | Section 2.1; root-cause framing.                                      |
| Slide 7: PESTEL and DPDP Act 2023 reference                            | Section 8; privacy and institutional review requirement.              |
| Slide 8: literature survey and product gap                             | Sections 1 and 2; student-started, requirement-first positioning.     |
| Slides 9–10: problem statement and objectives                          | Sections 3 and 9; goals and measurable outcomes.                      |
| Slide 11: profile, requirement, matching and connect; conceptual score | Sections 4–7; user journeys, requirements and proposed scoring model. |
| Slide 12: CATME case study and scale claims                            | Section 2.2; claims should be verified before external reuse.         |
| Slide 13: peer ratings, portfolio links, alerts and filters            | Sections 5 and 3.4; future scope / non-goals for MVP.                 |

End of document. This PRD is a draft based on the supplied presentation; proposed scoring weights, system architecture, acceptance criteria and pilot practices should be reviewed with the project team and faculty mentor before implementation.
