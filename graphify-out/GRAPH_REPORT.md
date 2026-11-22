# Graph Report - flick-app  (2026-11-22)

## Corpus Check
- 270 files · ~406,533 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 59 file(s) not represented in the graph (top: .csv 48, (none) 7, .example 2)

## Summary
- 4495 nodes · 9988 edges · 188 communities (97 shown, 91 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 1135 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4262e852`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- StreamingFilterAuditTests
- Defense-in-Depth Debugging Strategies
- test_guest_api.py
- models.py
- _make_movie
- apiRequest
- GuestConversionValidationAndRejectionTests
- WebSocketAuthenticationAndAuthorizationTests
- DiscoverPage.tsx
- vitest
- SessionDetailSerializer
- HardConstraints
- handle_catalogue_classification
- partnerWaitingBehavior.test.tsx
- run_staleness_sweep
- tutorialSystem.test.tsx
- DynamicMovieCatalogueTests
- .get_recommendations
- SpotlightTour.tsx
- compilerOptions
- HomePage.tsx
- Batch3WorkerIntegrationTests
- WebSocketRevocationTests
- TMDBRateLimiterInMemoryTests
- ClassicVaultEraFilterTests
- SessionLifecycleAndQuestionnaireRecoveryTests
- permissions.py
- MovieMutationsTestCase
- django_db
- Root Cause Tracing Techniques
- compilerOptions
- set_redis_client
- MatchConsumer
- Systematic Debugging
- manifest.json
- ProposalAPITestCase
- CatalogueJob
- .record_swipe_response
- FunctionalAndMobileAuditVerificationTests
- IntelligenceWorkerProcess
- backend/package.json
- UserPreferenceData
- settings.py
- _get_tmdb_request_headers
- ScreeningSessionResultsAndStatsPersistenceTests
- DesignSystemGenerator
- views.py
- AuthenticationAndPermissionTests
- PreferencesPage.tsx
- .agent/skills/ui-ux-pro-max/scripts/design_system.py
- api.ts
- DesignSystemGenerator
- test_frictionless_onboarding.py
- scripts
- 6. Flick-Specific Error Handling Architecture
- 2xx — Successful Responses
- React + TypeScript + Vite
- vercel.json
- Phase6BatchCRecentSessionsAndStreamingTests
- flick-frontend/package.json
- evaluate_eligibility_predicates
- tmdb_rate_limiter.py
- sw.js
- fetch_cached_tmdb
- GuestConversionRecoverySecurityTests
- tsconfig.json
- SessionJoiningTests
- GuestActivityTrackingTests
- SettingsSecurityTests
- HistoricalReconciliationService
- .recompute_user_taste_profile
- DiscoverTests
- HardConstraintFilter
- flick-frontend/package.json
- 9. Practical Troubleshooting Playbook
- PaginationAndResourceLimitTests
- Batch5PersonalizationEvaluationTests
- InteractionLog
- ui-ux-pro-max
- UserTasteProfile
- RecommendationDiscoveryTests
- ProposalExecutionWorker
- retrieval.py
- test_observability_and_security.py
- .authenticate
- PostgreSQLQueueConcurrencyTests
- ui-ux-pro-max
- .agents/skills/ui-ux-pro-max/scripts/design_system.py
- os
- TestCase
- IdentityLinkingService
- .claim_jobs
- Session
- .agent/skills/ui-ux-pro-max/scripts/search.py
- AuthenticationThrottlingTests
- production_settings.py
- Stage3EndToEndProductValidationTests
- ArchiveShelvesService
- tmdb_changes.py
- UniversalLocalNetworkDevConfigurationTests
- admin.py
- CuratorsSelectionView
- .claim_jobs
- LocalizedGenreRetrievalTests
- RegisterSerializer
- InteractionLogProcessingStatusTests
- SoundSynthesizer
- AdminCommandSecurityTests
- WatchlistTests
- Workflow Phases (Summary)
- AuthRateThrottle
- CorrelationIdMiddleware
- .generate_targeted_discovery_plan
- GuestThrottlingTests
- Pre1990ReleasePeriodFilterTests
- MovieSerializer
- eslint.config.js
- diagnose_lan_connectivity.sh
- CandidateRetrievalAndEligibilityTests
- SwipeUndoViewInverseParityTests
- TestIndianLanguageDiscovery
- Phase6BatchBBackendTests
- DeckStateAPITests
- compute_session_statistics
- _assert_safe_local_database
- middleware.py
- Command
- batch_sync_prelaunch.py
- SecretRedactionLoggerTests
- @testing-library/jest-dom
- interface
- SwipeFailureRecoveryAndEdgeCaseTests
- Examples
- 2xx — Successful Responses
- .agent/skills/ui-ux-pro-max/scripts/core.py
- PasswordResetSecurityTests
- SuperLikeReactionMatrixIntegrationTests
- SessionPage.tsx
- 5. Deep Dive: HTTP 304 Not Modified & Caching
- get_correlation_id
- Command
- .test_concurrent_duplicate_submissions_race_condition
- TMDBTimeoutError
- ThemeContext.tsx
- MotionAndSessionRegressionAuditTests
- calculate_preference_score
- UserIdentityLinkModelTests
- SessionCodeCollisionTests
- MatchListFilteringSecurityTests
- ConstraintExpansionProposal
- GuestConversionConcurrencyTests
- _validate_candidate
- CoreUserExperienceRepairTests
- vite.config.ts
- 4xx — Client-Side Errors
- RecentSessionsTests
- StreamingProvider
- .handle
- QueueLifecycleAndProvenanceCorrectionTest
- FrictionlessOnboardingConcurrencyTests
- vercel.json
- MovieTagRelation
- Flick — HTTP Status Codes, Server Logs & Error-Handling Reference
- CorrectSyntheticM1RecordsTest
- verify-batch-b-browser.js
- SessionHistoryTests
- ManifestCompilerService
- Batch 4: Historical Interaction Reconciliation & Identity Linking — Task List
- 7. Background Queue & Worker Numbers
- .test_concurrent_duplicate_submissions_by_single_user
- .handle
- UserProfile
- HistoricalReconciliationServiceTests
- enrichment_handlers.py
- 4. Deciphering Server Logs & Trailing Numbers
- InMemoryTokenBucket
- Command
- DatabaseConcurrencyAndSwipeReliabilityTests
- Movie

## God Nodes (most connected - your core abstractions)
1. `Movie` - 213 edges
2. `Session` - 136 edges
3. `Genre` - 99 edges
4. `Swipe` - 79 edges
5. `apiRequest()` - 78 edges
6. `UserPreferenceData` - 74 edges
7. `InteractionLog` - 67 edges
8. `HardConstraints` - 66 edges
9. `UserTasteProfile` - 60 edges
10. `CollaborativeAgreement` - 60 edges

## Surprising Connections (you probably didn't know these)
- `2. Secret Redaction Filter (`core/logging.py`)` --references--> `SecretRedactionFilter`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/logging.py
- `Anatomy of a Django/Daphne Access Log` --references--> `CorrelationIdMiddleware`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/middleware.py
- `Worker Leases, Fencing Tokens & Heartbeats` --references--> `StaleLeaseOwnershipError`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/services/catalogue_queue.py
- `HTTP 403 Forbidden` --references--> `transition_movie_classification()`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/services/movie_mutations.py
- `HTTP 429 Too Many Requests` --references--> `AuthRateThrottle`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/throttling.py

## Import Cycles
- None detected.

## Communities (188 total, 91 thin omitted)

### Community 1 - "Defense-in-Depth Debugging Strategies"
Cohesion: 0.06
Nodes (30): Boundary Testing, Checkpoint: Layered debugging complete, Cleanup and teardown, Defense-in-Depth Debugging Strategies, Dependency isolation, Divide and Conquer, Hypothesis Testing Protocol, Input validation (+22 more)

### Community 2 - "test_guest_api.py"
Cohesion: 0.03
Nodes (15): calculate_entropy_bits(), canonicalize_recovery_code(), compute_recovery_lookup_digest(), dummy_verify_recovery_code(), generate_recovery_code(), get_recovery_hmac_key(), hash_recovery_code(), verify_recovery_code() (+7 more)

### Community 3 - "models.py"
Cohesion: 0.09
Nodes (12): MovieManager, TmdbChangesCheckpoint, Meta, CatalogueQueueError, CatalogueQueueService, JobNotFoundError, StaleLeaseOwnershipError, StalenessSweepService (+4 more)

### Community 4 - "_make_movie"
Cohesion: 0.12
Nodes (4): _guard_pass(), _make_movie(), _mock_tmdb_response(), TMDBVerificationPipelineTest

### Community 5 - "apiRequest"
Cohesion: 0.07
Nodes (57): 1. The `ApiError` Class, 2. Automatic Error Message Extraction, 3. Automatic Session Expiration Handling (401 Interceptor), 4. Empty States vs. Actual Errors, Frontend Error Handling (`api.ts` & React), AccountSettingsPage, AnimatedRoutes(), AutoJoin (+49 more)

### Community 8 - "DiscoverPage.tsx"
Cohesion: 0.04
Nodes (67): BottomNav(), BottomNavProps, NavTab, CinemaHeader(), CinemaHeaderProps, backdropVariants, bottomSheetVariants, dialogVariants (+59 more)

### Community 9 - "vitest"
Cohesion: 0.05
Nodes (41): ErrorBoundary, Props, State, ConstraintExhaustionNoticeModal(), ConstraintExhaustionNoticeModalProps, ConstraintProposalData, DecisionInfo, parseDecision() (+33 more)

### Community 10 - "SessionDetailSerializer"
Cohesion: 0.05
Nodes (3): SessionDetailSerializer, Meta, AffinityEvaluationTests

### Community 11 - "HardConstraints"
Cohesion: 0.06
Nodes (6): CollaborativeAgreement, CandidatePool, HardConstraints, ManifestLearnedFeedbackIntegrationTests, ReproducibilityAndPersistenceTests, Phase1EndToEndScenarioTestCase

### Community 12 - "handle_catalogue_classification"
Cohesion: 0.08
Nodes (6): acquire_tmdb_token(), handle_catalogue_classification(), handle_catalogue_enrichment(), record_tmdb_429(), _tmdb_api_get(), TestIngestionAndProvenance

### Community 13 - "partnerWaitingBehavior.test.tsx"
Cohesion: 0.12
Nodes (14): AvatarStack(), RecentSession, SessionCard(), SessionsListPage(), guestSessionResponse, hostSessionData, hostSessionResponse, mockApiRequest (+6 more)

### Community 14 - "run_staleness_sweep"
Cohesion: 0.08
Nodes (4): StalenessSweepCheckpoint, Meta, run_staleness_sweep(), StalenessSweepTests

### Community 15 - "tutorialSystem.test.tsx"
Cohesion: 0.10
Nodes (28): ANON_ID_STORAGE_KEY, formatTourStorageKey(), generateAnonymousId(), getOrCreateAnonymousBrowserId(), getTourStatus(), getTourStorageKey(), hasSeenTour(), isTourCompletionStatus() (+20 more)

### Community 16 - "DynamicMovieCatalogueTests"
Cohesion: 0.08
Nodes (3): get_or_create_movie_from_tmdb(), DynamicMovieCatalogueTests, StreamingProviderAvailabilityTests

### Community 18 - "SpotlightTour.tsx"
Cohesion: 0.16
Nodes (18): ComputedLayout, computeTourLayout(), findVisibleTarget(), GestureHintCue(), getClampedTooltipWidth(), getViewportSize(), isFixedOrStickyElement(), isSameLayout() (+10 more)

### Community 19 - "compilerOptions"
Cohesion: 0.09
Nodes (21): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+13 more)

### Community 20 - "HomePage.tsx"
Cohesion: 0.11
Nodes (33): identifyUser(), resetAnalyticsIdentity(), convertGuestAccount(), AuthUser, clearAuthState, getCurrentUser(), isGuest(), isLoggedIn() (+25 more)

### Community 22 - "WebSocketRevocationTests"
Cohesion: 0.08
Nodes (8): broadcast_credential_revocation(), WebSocketRevocationTests, run(), run(), run(), run(), run(), run()

### Community 23 - "TMDBRateLimiterInMemoryTests"
Cohesion: 0.08
Nodes (3): parse_retry_after(), reset_rate_limiter(), TMDBRateLimiterInMemoryTests

### Community 26 - "permissions.py"
Cohesion: 0.15
Nodes (4): configure_sqlite_pragmas(), CoreConfig, CoreConfig, IsOwner

### Community 28 - "django_db"
Cohesion: 0.03
Nodes (42): Migration, Migration, Migration, Migration, Migration, Migration, Migration, Migration (+34 more)

### Community 29 - "Root Cause Tracing Techniques"
Cohesion: 0.07
Nodes (26): Checkpoint: When investigation is complete, Common Root Cause Patterns, Component Boundary Tracing, Configuration mismatch, Data Flow Analysis, Diff-based investigation, Error Message Anatomy, Example: Wrong calculation (+18 more)

### Community 30 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 31 - "set_redis_client"
Cohesion: 0.11
Nodes (3): set_redis_client(), TMDBRateLimiterProductionFailClosedTests, TMDBRateLimiterRedisLuaMockTests

### Community 33 - "Systematic Debugging"
Cohesion: 0.12
Nodes (15): Do not use this skill when, Examples, First move, Guardrails, Inputs to gather, Outputs, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis (+7 more)

### Community 34 - "manifest.json"
Cohesion: 0.12
Nodes (16): background_color, categories, description, display, icons, lang, name, orientation (+8 more)

### Community 36 - "CatalogueJob"
Cohesion: 0.17
Nodes (7): CatalogueJob, JobType, Meta, Status, handle_full_reconciliation(), handle_sync_changes_feed(), to_json_safe()

### Community 39 - "IntelligenceWorkerProcess"
Cohesion: 0.07
Nodes (4): Command, IntelligenceWorkerProcess, _beat(), register_handler()

### Community 40 - "backend/package.json"
Cohesion: 0.36
Nodes (7): devDependencies, autoprefixer@^10.4.23, postcss@^8.5.6, tailwindcss@^4.1.18, tailwindcss, autoprefixer, postcss

### Community 41 - "UserPreferenceData"
Cohesion: 0.04
Nodes (9): CollaborativeDeckScorer, ScoredCandidate, normalize_candidate_metadata(), rank_candidates_for_user(), IndividualRelevanceScorer, MovieIntelligenceData, UserPreferenceData, RoomRecommendationScenariosTestCase (+1 more)

### Community 43 - "_get_tmdb_request_headers"
Cohesion: 0.08
Nodes (22): _fetch(), format_tmdb_movie(), get_enhanced_movie_details(), get_genres_map(), get_movie_by_tmdb_id(), _fetch(), get_movie_genres(), get_now_playing_movies() (+14 more)

### Community 47 - "views.py"
Cohesion: 0.02
Nodes (51): StandardResultsSetPagination, SwipeHistoryPagination, DeckStateError, InvalidCardIndexError, StaleManifestError, ReplenishmentInProgressError, DeckCardDeliveryView, DeckSwipeResponseView (+43 more)

### Community 49 - "PreferencesPage.tsx"
Cohesion: 0.14
Nodes (14): OptionIcon(), PreferencesPage(), buildPreferences(), checkSessionState(), handleNext(), handleSubmit(), loadAuthoritativeState(), Question (+6 more)

### Community 50 - ".agent/skills/ui-ux-pro-max/scripts/design_system.py"
Cohesion: 0.14
Nodes (8): _detect_page_type(), format_ascii_box(), format_markdown(), format_master_md(), format_page_override_md(), generate_design_system(), _generate_intelligent_overrides(), persist_design_system()

### Community 51 - "api.ts"
Cohesion: 0.08
Nodes (35): AuthRecoveryPrompt(), AuthRecoveryPromptProps, ProvisionContinuationScreen(), ProvisionContinuationScreenProps, RecoveryCodeModal(), RecoveryCodeModalProps, acknowledgeRecovery(), ApiError (+27 more)

### Community 53 - "test_frictionless_onboarding.py"
Cohesion: 0.05
Nodes (25): GuestProfile, Meta, GuestProvisioningIdempotency, Meta, SessionChemistry, Meta, UserTasteSignal, Meta (+17 more)

### Community 54 - "scripts"
Cohesion: 0.33
Nodes (6): scripts, build, dev, lint, preview, test

### Community 55 - "6. Flick-Specific Error Handling Architecture"
Cohesion: 0.40
Nodes (5): 1. Custom Exception Handler (`backend/backend/exceptions.py`), 2. Secret Redaction Filter (`core/logging.py`), 3. Request Correlation ID Middleware (`core/middleware.py`), 6. Flick-Specific Error Handling Architecture, Backend Error Handling (DRF, Exceptions & Middleware)

### Community 56 - "2xx — Successful Responses"
Cohesion: 0.20
Nodes (10): 3. Complete HTTP Status Code Guide, 3xx — Redirection & Caching, 5xx — Server-Side & Upstream Errors, HTTP 301 Moved Permanently, HTTP 302 Found / Temporary Redirect, HTTP 304 Not Modified, HTTP 500 Internal Server Error, HTTP 502 Bad Gateway (+2 more)

### Community 57 - "React + TypeScript + Vite"
Cohesion: 0.50
Nodes (3): Expanding the ESLint configuration, React Compiler, React + TypeScript + Vite

### Community 59 - "Phase6BatchCRecentSessionsAndStreamingTests"
Cohesion: 0.08
Nodes (6): _create_tmdb_session(), get_tmdb_session(), reset_tmdb_session(), Phase6BatchCRecentSessionsAndStreamingTests, Phase6BatchCTMDBReliabilityTests, worker()

### Community 60 - "flick-frontend/package.json"
Cohesion: 0.15
Nodes (12): lucide-react@^0.577.0, material-symbols@^0.40.2, tailwindcss@^4.1.18, @types/node@^24.10.1, tailwindcss, name, private, type (+4 more)

### Community 61 - "evaluate_eligibility_predicates"
Cohesion: 0.06
Nodes (7): validate_movie_language(), MovieQuerySet, evaluate_eligibility_predicates(), EligibilityPredicatesOptionBTests, LanguageValidationTests, MovieEligibilityModelAndSignalTests, MovieQuerySetRestrictionTests

### Community 62 - "tmdb_rate_limiter.py"
Cohesion: 0.09
Nodes (11): get_movie_watch_providers(), acquire_tmdb_token(), calculate_cooldown_with_jitter(), get_rate_limiter_status(), get_redis_client(), is_production(), record_tmdb_429(), _redis_eval_acquire() (+3 more)

### Community 64 - "fetch_cached_tmdb"
Cohesion: 0.09
Nodes (3): fetch_cached_tmdb(), redact_sensitive_params(), TestReliabilityAndRetrieval

### Community 70 - "HistoricalReconciliationService"
Cohesion: 0.19
Nodes (6): HistoricalReconciliationService, map_swipe_reaction(), reconcile_historical_interactions(), Task 3: Historical Interaction Reconciliation Service & Command, Checkpoint 2: Reconciliation & Identity Complete, Phase 2: Reconciliation & Identity

### Community 74 - "flick-frontend/package.json"
Cohesion: 0.15
Nodes (13): devDependencies, jsdom@^30.1.3, @testing-library/react@^16.3.3, @types/canvas-confetti@^1.9.0, @types/react@^19.2.5, @types/react-dom@^19.2.3, typescript@~5.9.3, vitest@^5.1.0 (+5 more)

### Community 79 - "9. Practical Troubleshooting Playbook"
Cohesion: 0.12
Nodes (17): 10. `502 Bad Gateway`, 11. `503 Service Unavailable`, 12. `504 Gateway Timeout`, 13. `ConnectionResetError(54, 'Connection reset by peer')`, 14. `ECONNREFUSED 127.0.0.1:8000`, 15. `AbortError: The operation was aborted`, 16. `CatalogueJob status = failed_permanent`, 1. `200 55` (+9 more)

### Community 83 - "InteractionLog"
Cohesion: 0.04
Nodes (42): InteractionLog, Meta, MovieExposure, MovieKeyword, MovieTag, UserIdentityLink, LinkType, Meta (+34 more)

### Community 84 - "ui-ux-pro-max"
Cohesion: 0.07
Nodes (29): Accessibility, Available Domains, Available Stacks, Common Rules for Professional UI, Example Workflow, How to Use This Skill, Icons & Visual Elements, Interaction (+21 more)

### Community 87 - "ProposalExecutionWorker"
Cohesion: 0.04
Nodes (8): Command, ConstraintExpansionProposalSerializer, Meta, ProposalExecutionWorker, ProposalService, ProposalLifecycleAndIdempotencyTestCase, ProposalOutboxWorkerTestCase, ProposalServiceTestCase

### Community 88 - "retrieval.py"
Cohesion: 0.10
Nodes (13): SessionOccasionState, calculate_questionnaire_similarity(), calculate_screening_affinity(), calculate_session_statistics(), calculate_taste_compatibility(), normalize_user_preferences(), TransientReplenishmentError, CandidateRetrievalService (+5 more)

### Community 89 - "test_observability_and_security.py"
Cohesion: 0.12
Nodes (4): CorrelationIdFilter, SecretRedactionFilter, SecretRedactionFormatter, CorrelationIdConcurrencyTests

### Community 91 - "PostgreSQLQueueConcurrencyTests"
Cohesion: 0.12
Nodes (3): PostgreSQLQueueConcurrencyTests, do_enqueue(), worker_task()

### Community 92 - "ui-ux-pro-max"
Cohesion: 0.07
Nodes (29): Accessibility, Available Domains, Available Stacks, Common Rules for Professional UI, Example Workflow, How to Use This Skill, Icons & Visual Elements, Interaction (+21 more)

### Community 93 - ".agents/skills/ui-ux-pro-max/scripts/design_system.py"
Cohesion: 0.14
Nodes (8): _detect_page_type(), format_ascii_box(), format_markdown(), format_master_md(), format_page_override_md(), generate_design_system(), _generate_intelligent_overrides(), persist_design_system()

### Community 95 - "TestCase"
Cohesion: 0.09
Nodes (4): EmailVerificationTests, GenreIntegrationTests, LocalNetworkConfigurationTests, SessionLifecycleTests

### Community 98 - "Session"
Cohesion: 0.03
Nodes (28): Match, Meta, Session, SessionStats, Swipe, Meta, SessionSerializer, Meta (+20 more)

### Community 101 - "production_settings.py"
Cohesion: 0.16
Nodes (3): scrub_sentry_event(), scrub_value(), SentryScrubberTests

### Community 104 - "tmdb_changes.py"
Cohesion: 0.06
Nodes (5): Command, poll_tmdb_changes(), TmdbChangesService, PollTmdbChangesCommandTests, TmdbChangesServiceTests

### Community 106 - "admin.py"
Cohesion: 0.20
Nodes (11): CustomUserAdmin, GenreAdmin, MatchAdmin, MovieAdmin, MovieStreamingAvailabilityAdmin, SessionAdmin, SessionStatsAdmin, StreamingProviderAdmin (+3 more)

### Community 109 - "LocalizedGenreRetrievalTests"
Cohesion: 0.08
Nodes (3): LocalizedGenreRetrievalTests, fake_ingest(), fake_ingest()

### Community 115 - "Workflow Phases (Summary)"
Cohesion: 0.25
Nodes (7): Common Rationalisations, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis, Phase 3: Hypothesis and Testing, Phase 4: Implementation, Phases, Red Flags, and Common Rationalisations, Workflow Phases (Summary)

### Community 116 - "AuthRateThrottle"
Cohesion: 0.16
Nodes (6): AuthRateThrottle, GuestProvisionThrottle, GuestRecoverThrottle, GuestRecoveryKeyThrottle, PasswordResetRateThrottle, LoginView

### Community 117 - "CorrelationIdMiddleware"
Cohesion: 0.10
Nodes (4): reset_correlation_id(), set_correlation_id(), CorrelationIdMiddleware, CorrelationIdMiddlewareTests

### Community 122 - "MovieSerializer"
Cohesion: 0.09
Nodes (9): MovieSerializer, Meta, SwipeSerializer, Meta, DiscoverView, normalize_pair(), CompleteCatalogueView, _safe_analytics_callback() (+1 more)

### Community 123 - "eslint.config.js"
Cohesion: 0.15
Nodes (12): eslint@^9.39.1, @eslint/js@^9.39.1, eslint-plugin-react-hooks@^7.0.1, eslint-plugin-react-refresh@^0.4.24, globals@^16.5.0, typescript-eslint@^8.46.4, eslint, @eslint/js (+4 more)

### Community 125 - "CandidateRetrievalAndEligibilityTests"
Cohesion: 0.04
Nodes (3): FilmNoirClassifier, WorldCinemaClassifier, CandidateRetrievalAndEligibilityTests

### Community 131 - "_assert_safe_local_database"
Cohesion: 0.22
Nodes (5): _assert_safe_local_database(), _resolve_canonical_db_path(), SafetyGuardDebugFalseTest, SafetyGuardEngineTest, SafetyGuardPathTest

### Community 132 - "middleware.py"
Cohesion: 0.16
Nodes (4): get_user_from_token_key(), GuestActivityMiddleware, TokenAuthMiddleware, TokenAuthMiddlewareStack()

### Community 134 - "batch_sync_prelaunch.py"
Cohesion: 0.27
Nodes (3): Command, _make_session(), _tmdb_get()

### Community 137 - "interface"
Cohesion: 0.33
Nodes (5): interface, display_name, short_description, policy, allow_implicit_invocation

### Community 139 - "Examples"
Cohesion: 0.40
Nodes (4): Example 1: Test failure with stack trace, Example 2: Intermittent test failure, Example 3: Regression after a commit, Examples

### Community 140 - "2xx — Successful Responses"
Cohesion: 0.40
Nodes (5): 2xx — Successful Responses, HTTP 200 OK, HTTP 201 Created, HTTP 202 Accepted, HTTP 204 No Content

### Community 141 - ".agent/skills/ui-ux-pro-max/scripts/core.py"
Cohesion: 0.06
Nodes (12): BM25, detect_domain(), _load_csv(), search(), _search_csv(), search_stack(), BM25, detect_domain() (+4 more)

### Community 144 - "SessionPage.tsx"
Cohesion: 0.09
Nodes (38): DeckCardSkeleton(), MatchItemSkeleton(), MovieCardSkeleton(), ShelfSkeleton(), Skeleton(), SkeletonProps, StreamingItemSkeleton(), Provider (+30 more)

### Community 145 - "5. Deep Dive: HTTP 304 Not Modified & Caching"
Cohesion: 0.40
Nodes (5): 5. Deep Dive: HTTP 304 Not Modified & Caching, Conditional Requests (ETag & Last-Modified), How Browser Caching Works, How Caching Is Implemented in Flick, When 304 Is Healthy vs When It Is a Problem

### Community 146 - "get_correlation_id"
Cohesion: 0.17
Nodes (6): get_correlation_id(), run_all(), worker(), async_view(), __init__(), failing_view()

### Community 149 - "TMDBTimeoutError"
Cohesion: 0.12
Nodes (4): TMDBAPIError, TMDBServiceError, StreamingOptionsRemediationTests, MovieStreamingOptionsView

### Community 150 - "ThemeContext.tsx"
Cohesion: 0.08
Nodes (26): dependencies, canvas-confetti@^1.9.4, framer-motion@^12.31.0, posthog-js@^1.319.0, react@^19.2.0, react-dom@^19.2.0, react-router-dom@^7.12.0, App() (+18 more)

### Community 160 - "ConstraintExpansionProposal"
Cohesion: 0.08
Nodes (12): ConstraintExpansionProposal, Meta, ProposalOutboxMessage, Meta, ProposalError, ProposalExpiredError, ProposalInvalidStateError, ProposalNotFoundError (+4 more)

### Community 165 - "vite.config.ts"
Cohesion: 0.22
Nodes (6): @tailwindcss/vite@^4.1.18, vite@^7.2.4, @vitejs/plugin-react@^5.1.1, @tailwindcss/vite, vite, @vitejs/plugin-react

### Community 167 - "4xx — Client-Side Errors"
Cohesion: 0.17
Nodes (12): 4xx — Client-Side Errors, HTTP 400 Bad Request, HTTP 401 Unauthorized, HTTP 403 Forbidden, HTTP 404 Not Found, HTTP 405 Method Not Allowed, HTTP 408 Request Timeout, HTTP 409 Conflict (+4 more)

### Community 169 - "StreamingProvider"
Cohesion: 0.21
Nodes (5): Command, Command, MovieStreamingAvailability, Meta, StreamingProvider

### Community 173 - "QueueLifecycleAndProvenanceCorrectionTest"
Cohesion: 0.17
Nodes (3): DryRunImmutabilityTest, LimitValidationTest, QueueLifecycleAndProvenanceCorrectionTest

### Community 174 - "FrictionlessOnboardingConcurrencyTests"
Cohesion: 0.15
Nodes (6): FrictionlessOnboardingConcurrencyTests, worker(), worker(), worker(), merge_worker(), thread_b()

### Community 178 - "Flick — HTTP Status Codes, Server Logs & Error-Handling Reference"
Cohesion: 0.20
Nodes (9): 10. Glossary of Key Technical Terms, 1. Quick-Reference Cheat Sheet, 2. What Are HTTP Status Codes?, 8. Frontend & Build-Related Numbers, At a Glance: What Do These Numbers Mean?, Flick — HTTP Status Codes, Server Logs & Error-Handling Reference, Port Numbers, Table of Contents (+1 more)

### Community 179 - "CorrectSyntheticM1RecordsTest"
Cohesion: 0.15
Nodes (4): _resolve_staff_user(), _build_candidate_queryset(), CorrectSyntheticM1RecordsTest, _guard_pass()

### Community 180 - "verify-batch-b-browser.js"
Cohesion: 0.21
Nodes (5): puppeteer-core@^25.16.0, SCREENSHOT_DIR, SCREENSHOT_DIR, SCREENSHOT_DIR, puppeteer-core

### Community 183 - "ManifestCompilerService"
Cohesion: 0.05
Nodes (10): ActiveManifestImmutableError, HamiltonManifestAllocator, InsufficientCandidatesError, ManifestCompilationError, ManifestCompilerService, compute_learned_feedback_from_logs(), BoutiqueManifestCompilationTests, HamiltonManifestAllocatorTests (+2 more)

### Community 189 - "Batch 4: Historical Interaction Reconciliation & Identity Linking — Task List"
Cohesion: 0.50
Nodes (3): Batch 4: Historical Interaction Reconciliation & Identity Linking — Task List, Checkpoint 3: Batch 4 Complete, Phase 3: Durable Taste Engine & Tombstone Anonymization

### Community 190 - "7. Background Queue & Worker Numbers"
Cohesion: 0.40
Nodes (5): 7. Background Queue & Worker Numbers, Queue Priorities & Fair Scheduling Quotas, Retry Limits, Exponential Backoff & Quarantine, TMDB Dual-Bucket Rate Limiter Constants, Worker Leases, Fencing Tokens & Heartbeats

### Community 193 - "UserProfile"
Cohesion: 0.11
Nodes (4): UserProfile, ExistingRegisteredUserCompatibilityTests, GuestRecoveryConcurrencyTests, GuestProvisionView

### Community 202 - "enrichment_handlers.py"
Cohesion: 0.07
Nodes (7): _inspect_target_records(), check_deterministic_identity(), is_synthetic_movie(), normalize_title(), transition_movie_classification(), update_movie_metadata(), _validate_field_provenance_updates()

### Community 204 - "4. Deciphering Server Logs & Trailing Numbers"
Cohesion: 0.29
Nodes (7): 4. Deciphering Server Logs & Trailing Numbers, Anatomy of a Django/Daphne Access Log, What Do the Trailing Numbers Mean? (The 55 vs 1989 Mystery), Why does `/api/curators-selection/` show `200 1989`?, Why does `/api/users/profile/` show `200 55`?, Why does `GET /api/movies/` show `304 -` or `304 0`?, WSGI vs ASGI Logging Differences

### Community 211 - "InMemoryTokenBucket"
Cohesion: 0.15
Nodes (5): InMemoryTokenBucket, 1. The Movie Database (TMDB), 2. Redis, 3. PostgreSQL & SQLite, External Service Failure Modes (TMDB, Redis, Postgres)

### Community 262 - "Movie"
Cohesion: 0.05
Nodes (22): Command, Command, Command, Genre, Movie, GenreSerializer, Meta, ProposalOutboxMessageSerializer (+14 more)

## Knowledge Gaps
- **91 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Movie` connect `Movie` to `Phase6BatchBBackendTests`, `DeckStateAPITests`, `StreamingFilterAuditTests`, `models.py`, `_make_movie`, `batch_sync_prelaunch.py`, `SessionDetailSerializer`, `HardConstraints`, `handle_catalogue_classification`, `SwipeFailureRecoveryAndEdgeCaseTests`, `run_staleness_sweep`, `SuperLikeReactionMatrixIntegrationTests`, `DynamicMovieCatalogueTests`, `Batch3WorkerIntegrationTests`, `TMDBTimeoutError`, `MotionAndSessionRegressionAuditTests`, `ClassicVaultEraFilterTests`, `SessionLifecycleAndQuestionnaireRecoveryTests`, `MovieMutationsTestCase`, `MatchListFilteringSecurityTests`, `ConstraintExpansionProposal`, `_validate_candidate`, `CoreUserExperienceRepairTests`, `FunctionalAndMobileAuditVerificationTests`, `StreamingProvider`, `.handle`, `UserPreferenceData`, `ScreeningSessionResultsAndStatsPersistenceTests`, `FrictionlessOnboardingConcurrencyTests`, `QueueLifecycleAndProvenanceCorrectionTest`, `AuthenticationAndPermissionTests`, `views.py`, `CorrectSyntheticM1RecordsTest`, `test_frictionless_onboarding.py`, `SessionHistoryTests`, `ManifestCompilerService`, `Phase6BatchCRecentSessionsAndStreamingTests`, `evaluate_eligibility_predicates`, `.handle`, `fetch_cached_tmdb`, `HistoricalReconciliationServiceTests`, `DiscoverTests`, `HardConstraintFilter`, `enrichment_handlers.py`, `PaginationAndResourceLimitTests`, `Batch5PersonalizationEvaluationTests`, `InteractionLog`, `UserTasteProfile`, `RecommendationDiscoveryTests`, `ProposalExecutionWorker`, `retrieval.py`, `PostgreSQLQueueConcurrencyTests`, `DatabaseConcurrencyAndSwipeReliabilityTests`, `.claim_jobs`, `Session`, `Stage3EndToEndProductValidationTests`, `ArchiveShelvesService`, `tmdb_changes.py`, `admin.py`, `LocalizedGenreRetrievalTests`, `InteractionLogProcessingStatusTests`, `WatchlistTests`, `Pre1990ReleasePeriodFilterTests`, `MovieSerializer`, `CandidateRetrievalAndEligibilityTests`, `SwipeUndoViewInverseParityTests`, `TestIndianLanguageDiscovery`?**
  _High betweenness centrality (0.238) - this node is a cross-community bridge._
- **Are the 133 inferred relationships involving `Movie` (e.g. with `Command` and `Command`) actually correct?**
  _`Movie` has 133 INFERRED edges - model-reasoned connections that need verification._
- **Should `StreamingFilterAuditTests` be split into smaller, more focused modules?**
  _Cohesion score 0.09090909090909091 - nodes in this community are weakly interconnected._
- **Why does `6. Flick-Specific Error Handling Architecture` connect `6. Flick-Specific Error Handling Architecture` to `Flick — HTTP Status Codes, Server Logs & Error-Handling Reference`, `InMemoryTokenBucket`, `apiRequest`?**
  _High betweenness centrality (0.170) - this node is a cross-community bridge._
- **Are the 84 inferred relationships involving `Session` (e.g. with `MatchConsumer` and `SessionDetailSerializer`) actually correct?**
  _`Session` has 84 INFERRED edges - model-reasoned connections that need verification._
- **Should `Defense-in-Depth Debugging Strategies` be split into smaller, more focused modules?**
  _Cohesion score 0.06451612903225806 - nodes in this community are weakly interconnected._
- **Why does `Frontend Error Handling (`api.ts` & React)` connect `apiRequest` to `6. Flick-Specific Error Handling Architecture`?**
  _High betweenness centrality (0.170) - this node is a cross-community bridge._