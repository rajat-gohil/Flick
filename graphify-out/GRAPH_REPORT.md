# Graph Report - flick-app  (2026-11-19)

## Corpus Check
- 256 files · ~391,811 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 59 file(s) not represented in the graph (top: .csv 48, (none) 7, .example 2)

## Summary
- 4342 nodes · 9477 edges · 188 communities (91 shown, 97 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 1049 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0efd120e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- StreamingFilterAuditTests
- Defense-in-Depth Debugging Strategies
- test_guest_api.py
- django_db
- _make_movie
- router.tsx
- GuestConversionValidationAndRejectionTests
- WebSocketAuthenticationAndAuthorizationTests
- DiscoverPage.tsx
- api.ts
- CatalogueJob
- test_proposals.py
- HardConstraintFilter
- CinemaHeader
- run_staleness_sweep
- tutorialSystem.test.tsx
- DynamicMovieCatalogueTests
- ArchiveShelvesService
- SessionPage.tsx
- compilerOptions
- ProfilePage.tsx
- Batch3WorkerIntegrationTests
- WebSocketRevocationTests
- Pre1990ReleasePeriodFilterTests
- SessionLifecycleAndQuestionnaireRecoveryTests
- permissions.py
- MovieMutationsTestCase
- acquire_tmdb_token
- Root Cause Tracing Techniques
- compilerOptions
- RoomRecommendationScenariosTestCase
- MatchConsumer
- Systematic Debugging
- manifest.json
- ProposalAPITestCase
- Genre
- SuperLikeReactionMatrixIntegrationTests
- IndividualRelevanceScorer
- IntelligenceWorkerProcess
- backend/package.json
- ConstraintExhaustionNoticeModal.tsx
- .agents/skills/ui-ux-pro-max/scripts/core.py
- Phase6BatchCRecentSessionsAndStreamingTests
- ScreeningSessionResultsAndStatsPersistenceTests
- DesignSystemGenerator
- views.py
- IdentityLinkingService
- apiRequest
- .agent/skills/ui-ux-pro-max/scripts/design_system.py
- DiscoverTests
- DesignSystemGenerator
- Swipe
- scripts
- SecretRedactionFilter
- 2xx — Successful Responses
- React + TypeScript + Vite
- vercel.json
- StreamingProvider
- DeckAdvancementService
- evaluate_eligibility_predicates
- tmdb_rate_limiter.py
- sw.js
- ProposalExecutionWorker
- tsconfig.json
- evaluate_eligibility_predicates
- GuestActivityTrackingTests
- ClassicVaultEraFilterTests
- InteractionLog
- .agent/skills/ui-ux-pro-max/scripts/core.py
- FunctionalAndMobileAuditVerificationTests
- flick-frontend/package.json
- 9. Practical Troubleshooting Playbook
- .recompute_user_taste_profile
- .process_one_job
- Stage3EndToEndProductValidationTests
- RecommendationEvaluationTests
- ui-ux-pro-max
- UserTasteProfile
- .test_10_successful_deck_regeneration_after_approved_expansion
- HardConstraints
- CorrelationIdMiddleware
- PasswordResetSecurityTests
- PostgreSQLQueueConcurrencyTests
- ui-ux-pro-max
- .agents/skills/ui-ux-pro-max/scripts/design_system.py
- .score
- Movie
- set_redis_client
- .claim_jobs
- update_movie_metadata
- .agent/skills/ui-ux-pro-max/scripts/search.py
- AuthenticationThrottlingTests
- UserPreferenceData
- Phase6BatchCRecentSessionsAndStreamingTests
- TmdbChangesServiceTests
- UniversalLocalNetworkDevConfigurationTests
- admin.py
- TmdbChangesService
- .enqueue
- _tmdb_get
- AffinityEvaluationTests
- InteractionLogProcessingStatusTests
- SoundSynthesizer
- AdminCommandSecurityTests
- Workflow Phases (Summary)
- rank_candidates_for_user
- StalenessSweepCheckpoint
- Phase1EndToEndScenarioTestCase
- GuestThrottlingTests
- SecretRedactionLoggerTests
- SessionDetailSerializer
- eslint.config.js
- diagnose_lan_connectivity.sh
- HardConstraints
- _ingest_tmdb_results
- Phase6BatchBBackendTests
- _assert_safe_local_database
- middleware.py
- @testing-library/jest-dom
- retrieval.py
- batch3_handlers.py
- devDependencies
- interface
- PollTmdbChangesCommandTests
- Examples
- GuestRecoveryAPITests
- SessionPage.tsx
- Command
- BM25
- .record_swipe_response
- BM25
- ProposalLifecycleAndIdempotencyTestCase
- MotionAndSessionRegressionAuditTests
- SessionCodeCollisionTests
- MovieTagRelation
- MatchListFilteringSecurityTests
- TestIndianLanguageDiscovery
- ConstraintExpansionProposalSerializer
- GuestConversionConcurrencyTests
- _validate_candidate
- vite.config.ts
- get_correlation_id
- 4xx — Client-Side Errors
- reset_correlation_id
- ProposalOutboxWorkerTestCase
- TestCase
- poll_tmdb_changes.py
- vercel.json
- Flick — HTTP Status Codes, Server Logs & Error-Handling Reference
- CorrectSyntheticM1RecordsTest
- verify-batch-b-browser.js
- Match
- RecommendationDiscoveryTests
- .test_concurrent_duplicate_submissions_by_single_user
- EmailVerificationTests
- Command
- GuestActivityMiddleware
- .test_concurrent_duplicate_submissions_race_condition
- parse_retry_after
- 5. Deep Dive: HTTP 304 Not Modified & Caching
- HistoricalReconciliationService
- 4. Deciphering Server Logs & Trailing Numbers
- IntelligenceModelsTestCase
- InMemoryTokenBucket
- test_observability_and_security.py
- os
- DeckStateAPITests

## God Nodes (most connected - your core abstractions)
1. `Movie` - 209 edges
2. `Session` - 128 edges
3. `Genre` - 96 edges
4. `apiRequest()` - 76 edges
5. `UserPreferenceData` - 74 edges
6. `Swipe` - 71 edges
7. `HardConstraints` - 66 edges
8. `CollaborativeAgreement` - 60 edges
9. `InteractionLog` - 60 edges
10. `CatalogueJob` - 52 edges

## Surprising Connections (you probably didn't know these)
- `Anatomy of a Django/Daphne Access Log` --references--> `CorrelationIdMiddleware`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/middleware.py
- `Worker Leases, Fencing Tokens & Heartbeats` --references--> `StaleLeaseOwnershipError`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/services/catalogue_queue.py
- `2. Secret Redaction Filter (`core/logging.py`)` --references--> `SecretRedactionFilter`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/logging.py
- `Phase 3: Durable Taste Engine & Tombstone Anonymization` --references--> `UserTasteProfile`  [INFERRED]
  tasks/todo.md → backend/core/models.py
- `Architecture & Data Decisions` --references--> `InteractionLog`  [INFERRED]
  tasks/plan.md → backend/core/models.py

## Import Cycles
- None detected.

## Communities (188 total, 97 thin omitted)

### Community 1 - "Defense-in-Depth Debugging Strategies"
Cohesion: 0.06
Nodes (30): Boundary Testing, Checkpoint: Layered debugging complete, Cleanup and teardown, Defense-in-Depth Debugging Strategies, Dependency isolation, Divide and Conquer, Hypothesis Testing Protocol, Input validation (+22 more)

### Community 2 - "test_guest_api.py"
Cohesion: 0.04
Nodes (13): calculate_entropy_bits(), canonicalize_recovery_code(), compute_recovery_lookup_digest(), dummy_verify_recovery_code(), generate_recovery_code(), get_recovery_hmac_key(), hash_recovery_code(), verify_recovery_code() (+5 more)

### Community 3 - "django_db"
Cohesion: 0.03
Nodes (44): Migration, Migration, Migration, Migration, Migration, Migration, Migration, Migration (+36 more)

### Community 4 - "_make_movie"
Cohesion: 0.11
Nodes (5): DryRunImmutabilityTest, _guard_pass(), _make_movie(), _mock_tmdb_response(), TMDBVerificationPipelineTest

### Community 5 - "router.tsx"
Cohesion: 0.08
Nodes (41): App(), AccountSettingsPage, AnimatedRoutes(), AppRouter(), AutoJoin, CreateSessionPage, DiscoverPage, EntryPage (+33 more)

### Community 6 - "GuestConversionValidationAndRejectionTests"
Cohesion: 0.07
Nodes (3): GuestConversionRecoverySecurityTests, GuestConversionSuccessTests, GuestConversionValidationAndRejectionTests

### Community 8 - "DiscoverPage.tsx"
Cohesion: 0.05
Nodes (42): Provider, ProviderLogo(), streamingCache, StreamingData, StreamingOptions(), backdropVariants, bottomSheetVariants, dialogVariants (+34 more)

### Community 9 - "api.ts"
Cohesion: 0.04
Nodes (54): ErrorBoundary, Props, State, RecoveryCodeModal(), RecoveryCodeModalProps, acknowledgeRecovery(), ApiError, buildDeduplicationKey() (+46 more)

### Community 10 - "CatalogueJob"
Cohesion: 0.06
Nodes (20): Command, register_handler(), CatalogueJob, JobType, Meta, Status, MovieKeyword, CatalogueQueueError (+12 more)

### Community 11 - "test_proposals.py"
Cohesion: 0.06
Nodes (21): ConstraintExpansionProposal, Meta, ProposalOutboxMessage, Meta, GenreSerializer, Meta, ProposalOutboxMessageSerializer, Meta (+13 more)

### Community 13 - "CinemaHeader"
Cohesion: 0.11
Nodes (28): BottomNav(), BottomNavProps, NavTab, CinemaHeader(), CinemaHeaderProps, CreateSessionPage(), createSession(), Genre (+20 more)

### Community 15 - "tutorialSystem.test.tsx"
Cohesion: 0.09
Nodes (32): SpotlightTourStep, ThemeProvider(), ANON_ID_STORAGE_KEY, formatTourStorageKey(), generateAnonymousId(), getOrCreateAnonymousBrowserId(), getTourStatus(), getTourStorageKey() (+24 more)

### Community 17 - "ArchiveShelvesService"
Cohesion: 0.06
Nodes (6): ArchiveShelvesService, _movie_get(), _movie_getitem(), _pluralize_genre(), CuratorsSelectionView, YourArchiveView

### Community 18 - "SessionPage.tsx"
Cohesion: 0.10
Nodes (27): dependencies, canvas-confetti@^1.9.4, framer-motion@^12.31.0, posthog-js@^1.319.0, react@^19.2.0, react-dom@^19.2.0, react-router-dom@^7.12.0, ComputedLayout (+19 more)

### Community 19 - "compilerOptions"
Cohesion: 0.09
Nodes (21): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+13 more)

### Community 20 - "ProfilePage.tsx"
Cohesion: 0.11
Nodes (32): getPasswordStrength(), identifyUser(), resetAnalyticsIdentity(), convertGuestAccount(), AuthUser, clearAuthState, getCurrentUser(), isGuest() (+24 more)

### Community 22 - "WebSocketRevocationTests"
Cohesion: 0.08
Nodes (8): broadcast_credential_revocation(), WebSocketRevocationTests, run(), run(), run(), run(), run(), run()

### Community 26 - "permissions.py"
Cohesion: 0.15
Nodes (4): configure_sqlite_pragmas(), CoreConfig, CoreConfig, IsOwner

### Community 27 - "MovieMutationsTestCase"
Cohesion: 0.09
Nodes (3): transition_movie_classification(), MovieMutationsTestCase, HTTP 403 Forbidden

### Community 28 - "acquire_tmdb_token"
Cohesion: 0.09
Nodes (3): acquire_tmdb_token(), reset_rate_limiter(), TMDBRateLimiterInMemoryTests

### Community 29 - "Root Cause Tracing Techniques"
Cohesion: 0.07
Nodes (26): Checkpoint: When investigation is complete, Common Root Cause Patterns, Component Boundary Tracing, Configuration mismatch, Data Flow Analysis, Diff-based investigation, Error Message Anatomy, Example: Wrong calculation (+18 more)

### Community 30 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 31 - "RoomRecommendationScenariosTestCase"
Cohesion: 0.10
Nodes (3): CollaborativeDeckScorer, ScoredCandidate, RoomRecommendationScenariosTestCase

### Community 33 - "Systematic Debugging"
Cohesion: 0.12
Nodes (15): Do not use this skill when, Examples, First move, Guardrails, Inputs to gather, Outputs, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis (+7 more)

### Community 34 - "manifest.json"
Cohesion: 0.12
Nodes (16): background_color, categories, description, display, icons, lang, name, orientation (+8 more)

### Community 36 - "Genre"
Cohesion: 0.09
Nodes (7): Command, Command, Genre, MovieTag, fetch_tmdb_movies(), IntelligenceWorkerTasteHandlerTests, TasteEngineServiceTests

### Community 40 - "backend/package.json"
Cohesion: 0.36
Nodes (7): devDependencies, autoprefixer@^10.4.23, postcss@^8.5.6, tailwindcss@^4.1.18, tailwindcss, autoprefixer, postcss

### Community 41 - "ConstraintExhaustionNoticeModal.tsx"
Cohesion: 0.22
Nodes (16): ConstraintExhaustionNoticeModal(), ConstraintExhaustionNoticeModalProps, ConstraintProposalData, DecisionInfo, parseDecision(), CANONICAL_ERAS, CANONICAL_GENRES, CANONICAL_LANGUAGES (+8 more)

### Community 42 - ".agents/skills/ui-ux-pro-max/scripts/core.py"
Cohesion: 0.23
Nodes (5): detect_domain(), _load_csv(), search(), _search_csv(), search_stack()

### Community 43 - "Phase6BatchCRecentSessionsAndStreamingTests"
Cohesion: 0.13
Nodes (5): _create_tmdb_session(), get_tmdb_session(), reset_tmdb_session(), Phase6BatchCTMDBReliabilityTests, worker()

### Community 47 - "views.py"
Cohesion: 0.02
Nodes (59): Session, WatchlistItem, Meta, StandardResultsSetPagination, SwipeHistoryPagination, AuthRateThrottle, GuestProvisionThrottle, GuestRecoverThrottle (+51 more)

### Community 48 - "IdentityLinkingService"
Cohesion: 0.11
Nodes (6): IdentityLinkingServiceTests, Batch 4: Historical Interaction Reconciliation & Identity Linking — Task List, Checkpoint 2: Reconciliation & Identity Complete, Checkpoint 3: Batch 4 Complete, Phase 2: Reconciliation & Identity, Phase 3: Durable Taste Engine & Tombstone Anonymization

### Community 49 - "apiRequest"
Cohesion: 0.07
Nodes (38): 1. The `ApiError` Class, 2. Automatic Error Message Extraction, 3. Automatic Session Expiration Handling (401 Interceptor), 4. Empty States vs. Actual Errors, Frontend Error Handling (`api.ts` & React), apiRequest(), AccountSettingsPage(), handleChangeEmail() (+30 more)

### Community 50 - ".agent/skills/ui-ux-pro-max/scripts/design_system.py"
Cohesion: 0.14
Nodes (8): _detect_page_type(), format_ascii_box(), format_markdown(), format_master_md(), format_page_override_md(), generate_design_system(), _generate_intelligent_overrides(), persist_design_system()

### Community 53 - "Swipe"
Cohesion: 0.04
Nodes (18): SessionChemistry, Meta, Swipe, Meta, UserTasteSignal, Meta, MovieSerializer, Meta (+10 more)

### Community 54 - "scripts"
Cohesion: 0.33
Nodes (6): scripts, build, dev, lint, preview, test

### Community 55 - "SecretRedactionFilter"
Cohesion: 0.21
Nodes (6): SecretRedactionFilter, 1. Custom Exception Handler (`backend/backend/exceptions.py`), 2. Secret Redaction Filter (`core/logging.py`), 3. Request Correlation ID Middleware (`core/middleware.py`), 6. Flick-Specific Error Handling Architecture, Backend Error Handling (DRF, Exceptions & Middleware)

### Community 56 - "2xx — Successful Responses"
Cohesion: 0.13
Nodes (15): 2xx — Successful Responses, 3. Complete HTTP Status Code Guide, 3xx — Redirection & Caching, 5xx — Server-Side & Upstream Errors, HTTP 200 OK, HTTP 201 Created, HTTP 202 Accepted, HTTP 204 No Content (+7 more)

### Community 57 - "React + TypeScript + Vite"
Cohesion: 0.50
Nodes (3): Expanding the ESLint configuration, React Compiler, React + TypeScript + Vite

### Community 59 - "StreamingProvider"
Cohesion: 0.13
Nodes (7): Command, Command, MovieStreamingAvailability, Meta, StreamingProvider, _link_streaming_availability(), resolve_streaming_provider_ids()

### Community 60 - "DeckAdvancementService"
Cohesion: 0.06
Nodes (12): ConflictingResponseError, DeckAdvancementService, DeckStateError, InvalidCardIndexError, OutOfOrderResponseError, StaleManifestError, UndoNotPermittedError, DeckStateConcurrencyTests (+4 more)

### Community 61 - "evaluate_eligibility_predicates"
Cohesion: 0.06
Nodes (9): validate_movie_language(), Command, MovieQuerySet, movie_genres_changed_handler(), recalculate_movie_eligibility(), register_eligibility_signals(), LanguageValidationTests, MovieEligibilityModelAndSignalTests (+1 more)

### Community 62 - "tmdb_rate_limiter.py"
Cohesion: 0.15
Nodes (9): calculate_cooldown_with_jitter(), get_rate_limiter_status(), get_redis_client(), is_production(), record_tmdb_429(), _redis_eval_acquire(), _redis_eval_record_429(), _redis_eval_status() (+1 more)

### Community 65 - "ProposalExecutionWorker"
Cohesion: 0.15
Nodes (3): Command, ProposalExecutionWorker, ProposalOutboxProcessBatchView

### Community 71 - "InteractionLog"
Cohesion: 0.04
Nodes (39): InteractionLog, Meta, MovieExposure, UserIdentityLink, LinkType, Meta, UserTasteProfile, DuplicateIdentityLinkError (+31 more)

### Community 72 - ".agent/skills/ui-ux-pro-max/scripts/core.py"
Cohesion: 0.20
Nodes (5): detect_domain(), _load_csv(), search(), _search_csv(), search_stack()

### Community 74 - "flick-frontend/package.json"
Cohesion: 0.15
Nodes (12): lucide-react@^0.577.0, material-symbols@^0.40.2, tailwindcss@^4.1.18, @types/node@^24.10.1, tailwindcss, name, private, type (+4 more)

### Community 79 - "9. Practical Troubleshooting Playbook"
Cohesion: 0.12
Nodes (17): 10. `502 Bad Gateway`, 11. `503 Service Unavailable`, 12. `504 Gateway Timeout`, 13. `ConnectionResetError(54, 'Connection reset by peer')`, 14. `ECONNREFUSED 127.0.0.1:8000`, 15. `AbortError: The operation was aborted`, 16. `CatalogueJob status = failed_permanent`, 1. `200 55` (+9 more)

### Community 84 - "ui-ux-pro-max"
Cohesion: 0.07
Nodes (29): Accessibility, Available Domains, Available Stacks, Common Rules for Professional UI, Example Workflow, How to Use This Skill, Icons & Visual Elements, Interaction (+21 more)

### Community 88 - "HardConstraints"
Cohesion: 0.03
Nodes (19): CollaborativeAgreement, SessionOccasionState, ActiveManifestImmutableError, HamiltonManifestAllocator, InsufficientCandidatesError, ManifestCompilationError, ManifestCompilerService, ReplenishmentInProgressError (+11 more)

### Community 90 - "PasswordResetSecurityTests"
Cohesion: 0.06
Nodes (4): EmailOrUsernameModelBackend, AuthenticationLoggingSecurityTests, PasswordResetSecurityTests, LoginView

### Community 91 - "PostgreSQLQueueConcurrencyTests"
Cohesion: 0.12
Nodes (3): PostgreSQLQueueConcurrencyTests, do_enqueue(), worker_task()

### Community 92 - "ui-ux-pro-max"
Cohesion: 0.07
Nodes (29): Accessibility, Available Domains, Available Stacks, Common Rules for Professional UI, Example Workflow, How to Use This Skill, Icons & Visual Elements, Interaction (+21 more)

### Community 93 - ".agents/skills/ui-ux-pro-max/scripts/design_system.py"
Cohesion: 0.14
Nodes (8): _detect_page_type(), format_ascii_box(), format_markdown(), format_master_md(), format_page_override_md(), generate_design_system(), _generate_intelligent_overrides(), persist_design_system()

### Community 94 - ".score"
Cohesion: 0.11
Nodes (3): normalize_candidate_metadata(), MovieIntelligenceData, ScoringServiceTestCase

### Community 95 - "Movie"
Cohesion: 0.02
Nodes (24): Movie, SessionStats, get_movie_watch_providers(), TMDBAPIError, TMDBServiceError, TMDBTimeoutError, Phase6BatchBConcurrencyTests, StreamingOptionsRemediationTests (+16 more)

### Community 96 - "set_redis_client"
Cohesion: 0.10
Nodes (3): set_redis_client(), TMDBRateLimiterProductionFailClosedTests, TMDBRateLimiterRedisLuaMockTests

### Community 99 - ".agent/skills/ui-ux-pro-max/scripts/search.py"
Cohesion: 0.11
Nodes (4): format_output(), format_output(), main(), start.sh script

### Community 106 - "admin.py"
Cohesion: 0.20
Nodes (11): CustomUserAdmin, GenreAdmin, MatchAdmin, MovieAdmin, MovieStreamingAvailabilityAdmin, SessionAdmin, SessionStatsAdmin, StreamingProviderAdmin (+3 more)

### Community 109 - "_tmdb_get"
Cohesion: 0.21
Nodes (3): Command, _make_session(), _tmdb_get()

### Community 110 - "AffinityEvaluationTests"
Cohesion: 0.07
Nodes (6): calculate_questionnaire_similarity(), calculate_screening_affinity(), calculate_session_statistics(), calculate_taste_compatibility(), normalize_user_preferences(), AffinityEvaluationTests

### Community 115 - "Workflow Phases (Summary)"
Cohesion: 0.25
Nodes (7): Common Rationalisations, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis, Phase 3: Hypothesis and Testing, Phase 4: Implementation, Phases, Red Flags, and Common Rationalisations, Workflow Phases (Summary)

### Community 116 - "rank_candidates_for_user"
Cohesion: 0.18
Nodes (3): compute_learned_feedback_from_logs(), rank_candidates_for_user(), ScoringResult

### Community 123 - "eslint.config.js"
Cohesion: 0.15
Nodes (12): eslint@^9.39.1, @eslint/js@^9.39.1, eslint-plugin-react-hooks@^7.0.1, eslint-plugin-react-refresh@^0.4.24, globals@^16.5.0, typescript-eslint@^8.46.4, eslint, @eslint/js (+4 more)

### Community 125 - "HardConstraints"
Cohesion: 0.05
Nodes (3): FilmNoirClassifier, WorldCinemaClassifier, CandidateRetrievalAndEligibilityTests

### Community 127 - "_ingest_tmdb_results"
Cohesion: 0.07
Nodes (3): _ingest_tmdb_results(), TestIngestionAndProvenance, TestReliabilityAndRetrieval

### Community 131 - "_assert_safe_local_database"
Cohesion: 0.19
Nodes (6): _assert_safe_local_database(), _resolve_canonical_db_path(), QueueLifecycleAndProvenanceCorrectionTest, SafetyGuardDebugFalseTest, SafetyGuardEngineTest, SafetyGuardPathTest

### Community 132 - "middleware.py"
Cohesion: 0.15
Nodes (3): get_user_from_token_key(), TokenAuthMiddleware, TokenAuthMiddlewareStack()

### Community 134 - "retrieval.py"
Cohesion: 0.05
Nodes (29): StalenessSweepService, discover_movies(), _fetch(), fetch_cached_tmdb(), format_tmdb_movie(), get_enhanced_movie_details(), get_genres_map(), get_movie_by_tmdb_id() (+21 more)

### Community 135 - "batch3_handlers.py"
Cohesion: 0.26
Nodes (3): handle_full_reconciliation(), handle_sync_changes_feed(), to_json_safe()

### Community 136 - "devDependencies"
Cohesion: 0.15
Nodes (13): devDependencies, jsdom@^30.1.3, @testing-library/react@^16.3.3, @types/canvas-confetti@^1.9.0, @types/react@^19.2.5, @types/react-dom@^19.2.3, typescript@~5.9.3, vitest@^5.1.0 (+5 more)

### Community 137 - "interface"
Cohesion: 0.33
Nodes (5): interface, display_name, short_description, policy, allow_implicit_invocation

### Community 139 - "Examples"
Cohesion: 0.40
Nodes (4): Example 1: Test failure with stack trace, Example 2: Intermittent test failure, Example 3: Regression after a commit, Examples

### Community 142 - "GuestRecoveryAPITests"
Cohesion: 0.05
Nodes (7): GuestProfile, Meta, UserProfile, ExistingRegisteredUserCompatibilityTests, GuestProvisioningAPITests, GuestRecoveryAPITests, GuestRecoveryConcurrencyTests

### Community 144 - "SessionPage.tsx"
Cohesion: 0.09
Nodes (39): DeckCardSkeleton(), MatchItemSkeleton(), MovieCardSkeleton(), ShelfSkeleton(), Skeleton(), SkeletonProps, StreamingItemSkeleton(), trackEvent() (+31 more)

### Community 159 - "TestIndianLanguageDiscovery"
Cohesion: 0.08
Nodes (4): DiscoveryQuerySpec, IndianCatalogueCoverageReport, IndianCatalogueDiscoveryService, TestIndianLanguageDiscovery

### Community 162 - "_validate_candidate"
Cohesion: 0.20
Nodes (3): Command, _validate_candidate(), CandidatePrevalidationTest

### Community 165 - "vite.config.ts"
Cohesion: 0.22
Nodes (6): @tailwindcss/vite@^4.1.18, vite@^7.2.4, @vitejs/plugin-react@^5.1.1, @tailwindcss/vite, vite, @vitejs/plugin-react

### Community 166 - "get_correlation_id"
Cohesion: 0.17
Nodes (6): get_correlation_id(), run_all(), worker(), async_view(), __init__(), failing_view()

### Community 167 - "4xx — Client-Side Errors"
Cohesion: 0.20
Nodes (10): 4xx — Client-Side Errors, HTTP 400 Bad Request, HTTP 401 Unauthorized, HTTP 404 Not Found, HTTP 405 Method Not Allowed, HTTP 408 Request Timeout, HTTP 409 Conflict, HTTP 413 Content Too Large (+2 more)

### Community 168 - "reset_correlation_id"
Cohesion: 0.17
Nodes (3): reset_correlation_id(), set_correlation_id(), TMDBOutboundHeaderPropagationTests

### Community 175 - "poll_tmdb_changes.py"
Cohesion: 0.19
Nodes (4): Command, PollerLockedError, RateLimitBackoffError, StalePollerOwnershipError

### Community 178 - "Flick — HTTP Status Codes, Server Logs & Error-Handling Reference"
Cohesion: 0.13
Nodes (14): 10. Glossary of Key Technical Terms, 1. Quick-Reference Cheat Sheet, 2. What Are HTTP Status Codes?, 7. Background Queue & Worker Numbers, 8. Frontend & Build-Related Numbers, At a Glance: What Do These Numbers Mean?, Flick — HTTP Status Codes, Server Logs & Error-Handling Reference, Port Numbers (+6 more)

### Community 179 - "CorrectSyntheticM1RecordsTest"
Cohesion: 0.11
Nodes (6): Command, _inspect_target_records(), _resolve_staff_user(), _build_candidate_queryset(), CorrectSyntheticM1RecordsTest, _guard_pass()

### Community 180 - "verify-batch-b-browser.js"
Cohesion: 0.21
Nodes (5): puppeteer-core@^25.16.0, SCREENSHOT_DIR, SCREENSHOT_DIR, SCREENSHOT_DIR, puppeteer-core

### Community 182 - "Match"
Cohesion: 0.06
Nodes (6): Match, Meta, EligibilityPolicyEngine, GuestConversionDataIntegrityTests, SuperLikePersistenceAndAttributionTests, SessionHistoryTests

### Community 196 - "5. Deep Dive: HTTP 304 Not Modified & Caching"
Cohesion: 0.40
Nodes (5): 5. Deep Dive: HTTP 304 Not Modified & Caching, Conditional Requests (ETag & Last-Modified), How Browser Caching Works, How Caching Is Implemented in Flick, When 304 Is Healthy vs When It Is a Problem

### Community 201 - "HistoricalReconciliationService"
Cohesion: 0.06
Nodes (7): HistoricalReconciliationService, map_swipe_reaction(), reconcile_historical_interactions(), HistoricalReconciliationServiceTests, SwipeUndoViewInverseParityTests, UserIdentityLinkModelTests, Task 3: Historical Interaction Reconciliation Service & Command

### Community 204 - "4. Deciphering Server Logs & Trailing Numbers"
Cohesion: 0.29
Nodes (7): 4. Deciphering Server Logs & Trailing Numbers, Anatomy of a Django/Daphne Access Log, What Do the Trailing Numbers Mean? (The 55 vs 1989 Mystery), Why does `/api/curators-selection/` show `200 1989`?, Why does `/api/users/profile/` show `200 55`?, Why does `GET /api/movies/` show `304 -` or `304 0`?, WSGI vs ASGI Logging Differences

### Community 211 - "InMemoryTokenBucket"
Cohesion: 0.15
Nodes (5): InMemoryTokenBucket, 1. The Movie Database (TMDB), 2. Redis, 3. PostgreSQL & SQLite, External Service Failure Modes (TMDB, Redis, Postgres)

### Community 219 - "test_observability_and_security.py"
Cohesion: 0.15
Nodes (3): CorrelationIdFilter, SecretRedactionFormatter, CorrelationIdConcurrencyTests

## Knowledge Gaps
- **97 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Movie` connect `Movie` to `Phase6BatchBBackendTests`, `StreamingFilterAuditTests`, `django_db`, `_make_movie`, `_assert_safe_local_database`, `retrieval.py`, `CatalogueJob`, `test_proposals.py`, `HardConstraintFilter`, `PollTmdbChangesCommandTests`, `run_staleness_sweep`, `DeckStateAPITests`, `ArchiveShelvesService`, `DynamicMovieCatalogueTests`, `Batch3WorkerIntegrationTests`, `ProposalLifecycleAndIdempotencyTestCase`, `MotionAndSessionRegressionAuditTests`, `Pre1990ReleasePeriodFilterTests`, `SessionLifecycleAndQuestionnaireRecoveryTests`, `MovieMutationsTestCase`, `MatchListFilteringSecurityTests`, `RoomRecommendationScenariosTestCase`, `TestIndianLanguageDiscovery`, `_validate_candidate`, `Genre`, `SuperLikeReactionMatrixIntegrationTests`, `IndividualRelevanceScorer`, `ProposalOutboxWorkerTestCase`, `ScreeningSessionResultsAndStatsPersistenceTests`, `TestCase`, `views.py`, `CorrectSyntheticM1RecordsTest`, `DiscoverTests`, `Swipe`, `Match`, `RecommendationDiscoveryTests`, `StreamingProvider`, `DeckAdvancementService`, `evaluate_eligibility_predicates`, `ClassicVaultEraFilterTests`, `InteractionLog`, `HistoricalReconciliationService`, `FunctionalAndMobileAuditVerificationTests`, `.recompute_user_taste_profile`, `IntelligenceModelsTestCase`, `Stage3EndToEndProductValidationTests`, `RecommendationEvaluationTests`, `UserTasteProfile`, `HardConstraints`, `PostgreSQLQueueConcurrencyTests`, `.score`, `.claim_jobs`, `update_movie_metadata`, `UserPreferenceData`, `Phase6BatchCRecentSessionsAndStreamingTests`, `TmdbChangesServiceTests`, `admin.py`, `TmdbChangesService`, `_tmdb_get`, `AffinityEvaluationTests`, `InteractionLogProcessingStatusTests`, `rank_candidates_for_user`, `Phase1EndToEndScenarioTestCase`, `HardConstraints`, `_ingest_tmdb_results`?**
  _High betweenness centrality (0.269) - this node is a cross-community bridge._
- **Are the 130 inferred relationships involving `Movie` (e.g. with `Command` and `Command`) actually correct?**
  _`Movie` has 130 INFERRED edges - model-reasoned connections that need verification._
- **Should `Defense-in-Depth Debugging Strategies` be split into smaller, more focused modules?**
  _Cohesion score 0.06451612903225806 - nodes in this community are weakly interconnected._
- **Why does `6. Flick-Specific Error Handling Architecture` connect `SecretRedactionFilter` to `apiRequest`, `Flick — HTTP Status Codes, Server Logs & Error-Handling Reference`, `InMemoryTokenBucket`?**
  _High betweenness centrality (0.172) - this node is a cross-community bridge._
- **Are the 79 inferred relationships involving `Session` (e.g. with `MatchConsumer` and `SessionDetailSerializer`) actually correct?**
  _`Session` has 79 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_guest_api.py` be split into smaller, more focused modules?**
  _Cohesion score 0.035346097201767304 - nodes in this community are weakly interconnected._
- **Why does `Frontend Error Handling (`api.ts` & React)` connect `apiRequest` to `SecretRedactionFilter`?**
  _High betweenness centrality (0.171) - this node is a cross-community bridge._