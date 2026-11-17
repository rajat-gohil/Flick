# Graph Report - flick-app  (2026-11-17)

## Corpus Check
- 245 files · ~292,111 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 59 file(s) not represented in the graph (top: .csv 48, (none) 7, .example 2)

## Summary
- 4222 nodes · 9119 edges · 188 communities (89 shown, 99 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 1036 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e4067b71`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- HardConstraintFilter
- Defense-in-Depth Debugging Strategies
- guest_security.py
- django_db
- _make_movie
- router.tsx
- GuestConversionValidationAndRejectionTests
- WebSocketAuthenticationAndAuthorizationTests
- DiscoverPage.tsx
- .get_recommendations
- .create_proposal
- SessionPageInner
- django_db_models_deletion
- CinemaHeader
- Movie
- Batch5PersonalizationEvaluationTests
- DynamicMovieCatalogueTests
- test_observability_and_security.py
- apiRequest
- compilerOptions
- ConstraintExhaustionNoticeModal.tsx
- GuestProfile
- WebSocketRevocationTests
- ProposalExecutionWorker
- Pre1990ReleasePeriodFilterTests
- SessionLifecycleAndQuestionnaireRecoveryTests
- permissions.py
- transition_movie_classification
- batch3_handlers.py
- Root Cause Tracing Techniques
- compilerOptions
- TMDBRateLimiterInMemoryTests
- MatchConsumer
- Systematic Debugging
- manifest.json
- ProposalAPITestCase
- AffinityEvaluationTests
- CollaborativeAgreement
- evaluate_eligibility_predicates
- PasswordResetSecurityTests
- backend/package.json
- handle_catalogue_classification
- TmdbChangesServiceTests
- GuestProvisioningAPITests
- RecoveryHandoffReliabilityTests
- ScreeningSessionResultsAndStatsPersistenceTests
- DesignSystemGenerator
- Session
- requests
- CatalogueJob
- .agent/skills/ui-ux-pro-max/scripts/design_system.py
- SwipeUndoViewInverseParityTests
- DesignSystemGenerator
- GuestRecoveryConcurrencyTests
- scripts
- 6. Flick-Specific Error Handling Architecture
- 5xx — Server-Side & Upstream Errors
- React + TypeScript + Vite
- vercel.json
- tmdb.py
- .enqueue
- tmdb.py
- sw.js
- ConstraintExpansionProposal
- test_proposals.py
- tsconfig.json
- calculate_questionnaire_similarity
- GuestActivityTrackingTests
- InteractionLog
- .agent/skills/ui-ux-pro-max/scripts/core.py
- 9. Practical Troubleshooting Playbook
- admin.py
- ArchiveShelvesService
- models.py
- .complete_job
- ui-ux-pro-max
- api.ts
- HardConstraints
- ui-ux-pro-max
- .agents/skills/ui-ux-pro-max/scripts/design_system.py
- enrichment_handlers.py
- .recompute_user_taste_profile
- set_redis_client
- .agent/skills/ui-ux-pro-max/scripts/search.py
- AuthenticationAndPermissionTests
- UniversalLocalNetworkDevConfigurationTests
- .calculate_allocation
- Phase6BatchCTMDBReliabilityTests
- SessionDetailSerializer
- .record_swipe_response
- SessionPage.tsx
- Workflow Phases (Summary)
- UserPreferenceData
- TestIngestionAndProvenance
- FunctionalAndMobileAuditVerificationTests
- diagnose_lan_connectivity.sh
- CandidateRetrievalAndEligibilityTests
- CoreUserExperienceRepairTests
- Phase6BatchBBackendTests
- tests.py
- GuestActivityMiddleware
- eslint.config.js
- interface
- .authenticate
- Examples
- Batch3WorkerIntegrationTests
- SwipeAndMatchingTests
- HomePage.tsx
- devDependencies
- views.py
- MatchListFilteringSecurityTests
- GuestConversionConcurrencyTests
- ExistingRegisteredUserCompatibilityTests
- 4xx — Client-Side Errors
- SwipeUndoTests
- flick-frontend/package.json
- _assert_safe_local_database
- Flick — HTTP Status Codes, Server Logs & Error-Handling Reference
- CorrectSyntheticM1RecordsTest
- verify-batch-b-browser.js
- 2xx — Successful Responses
- vite.config.ts
- LocalizedGenreRetrievalTests
- IntelligenceWorkerProcess
- CatalogueQueueService
- WatchlistItem
- AdminCommandSecurityTests
- parse_retry_after
- 5. Deep Dive: HTTP 304 Not Modified & Caching
- GuestRecoveryAPITests
- .link_guest_to_user
- .handle
- HistoricalReconciliationService
- PostgreSQLQueueConcurrencyTests
- .handle
- 4. Deciphering Server Logs & Trailing Numbers
- TestIndianLanguageDiscovery
- SessionJoiningTests
- IntelligenceModelsTestCase
- StreamingOptionsRemediationTests
- InMemoryTokenBucket
- SettingsSecurityTests
- test_observability_and_security.py
- InteractionLogProcessingStatusTests
- Phase1EndToEndScenarioTestCase
- .generate_targeted_discovery_plan
- GuestConversionRecoverySecurityTests
- _validate_candidate
- BoutiqueManifestCompilationTests
- SuperLikePersistenceAndAttributionTests
- UserTasteProfile
- GuestProfileModelTests
- DatabaseConcurrencyAndSwipeReliabilityTests
- run_staleness_sweep
- MotionAndSessionRegressionAuditTests
- Match
- Command
- TestReliabilityAndRetrieval
- retrieval.py
- Command
- LimitValidationTest
- ProposalLifecycleAndIdempotencyTestCase
- DeckStateAPITests
- @testing-library/jest-dom

## God Nodes (most connected - your core abstractions)
1. `Movie` - 206 edges
2. `Session` - 126 edges
3. `Genre` - 94 edges
4. `apiRequest()` - 75 edges
5. `UserPreferenceData` - 74 edges
6. `Swipe` - 71 edges
7. `HardConstraints` - 62 edges
8. `CollaborativeAgreement` - 60 edges
9. `InteractionLog` - 60 edges
10. `CatalogueJob` - 52 edges

## Surprising Connections (you probably didn't know these)
- `2. Secret Redaction Filter (`core/logging.py`)` --references--> `SecretRedactionFilter`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/logging.py
- `Anatomy of a Django/Daphne Access Log` --references--> `CorrelationIdMiddleware`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/middleware.py
- `Worker Leases, Fencing Tokens & Heartbeats` --references--> `StaleLeaseOwnershipError`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/services/catalogue_queue.py
- `HTTP 403 Forbidden` --references--> `transition_movie_classification()`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/services/movie_mutations.py
- `Phase 3: Durable Taste Engine & Tombstone Anonymization` --references--> `UserTasteProfile`  [INFERRED]
  tasks/todo.md → backend/core/models.py

## Import Cycles
- None detected.

## Communities (188 total, 99 thin omitted)

### Community 1 - "Defense-in-Depth Debugging Strategies"
Cohesion: 0.06
Nodes (30): Boundary Testing, Checkpoint: Layered debugging complete, Cleanup and teardown, Defense-in-Depth Debugging Strategies, Dependency isolation, Divide and Conquer, Hypothesis Testing Protocol, Input validation (+22 more)

### Community 2 - "guest_security.py"
Cohesion: 0.05
Nodes (11): calculate_entropy_bits(), canonicalize_recovery_code(), compute_recovery_lookup_digest(), dummy_verify_recovery_code(), generate_recovery_code(), get_recovery_hmac_key(), hash_recovery_code(), verify_recovery_code() (+3 more)

### Community 3 - "django_db"
Cohesion: 0.04
Nodes (24): Migration, Migration, Migration, Migration, Migration, Migration, Migration, Migration (+16 more)

### Community 4 - "_make_movie"
Cohesion: 0.11
Nodes (5): DryRunImmutabilityTest, _guard_pass(), _make_movie(), _mock_tmdb_response(), TMDBVerificationPipelineTest

### Community 5 - "router.tsx"
Cohesion: 0.08
Nodes (38): App(), AccountSettingsPage, AnimatedRoutes(), AppRouter(), AutoJoin, CreateSessionPage, DiscoverPage, EntryPage (+30 more)

### Community 8 - "DiscoverPage.tsx"
Cohesion: 0.06
Nodes (37): DeckCardSkeleton(), MatchItemSkeleton(), MovieCardSkeleton(), ShelfSkeleton(), Skeleton(), SkeletonProps, StreamingItemSkeleton(), Provider (+29 more)

### Community 10 - ".create_proposal"
Cohesion: 0.09
Nodes (3): ProposalService, fake_ingest(), ProposalServiceTestCase

### Community 11 - "SessionPageInner"
Cohesion: 0.11
Nodes (29): trackEvent(), getWsBaseUrl(), getWsUrl(), prefersReducedMotion(), CreateSessionPage(), createSession(), Genre, getGenreIcon() (+21 more)

### Community 12 - "django_db_models_deletion"
Cohesion: 0.07
Nodes (14): Migration, Migration, Migration, Migration, Migration, Migration, Migration, Migration (+6 more)

### Community 13 - "CinemaHeader"
Cohesion: 0.15
Nodes (23): BottomNav(), BottomNavProps, NavTab, CinemaHeader(), CinemaHeaderProps, DEFAULT_PREFS, NotificationsSettingsPage(), requestPushPermission() (+15 more)

### Community 14 - "Movie"
Cohesion: 0.10
Nodes (8): Command, Movie, MovieExposure, _movie_contains(), _movie_get(), _movie_getitem(), PersonalizedRecommendationEngine, GuestConversionDataIntegrityTests

### Community 17 - "test_observability_and_security.py"
Cohesion: 0.05
Nodes (17): get_correlation_id(), reset_correlation_id(), SecretRedactionFormatter, set_correlation_id(), CorrelationIdMiddleware, get_user_from_token_key(), TokenAuthMiddleware, TokenAuthMiddlewareStack() (+9 more)

### Community 18 - "apiRequest"
Cohesion: 0.07
Nodes (36): 1. The `ApiError` Class, 3. Automatic Session Expiration Handling (401 Interceptor), 4. Empty States vs. Actual Errors, Frontend Error Handling (`api.ts` & React), apiRequest(), AccountSettingsPage(), handleChangeEmail(), handleChangePassword() (+28 more)

### Community 19 - "compilerOptions"
Cohesion: 0.09
Nodes (21): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+13 more)

### Community 20 - "ConstraintExhaustionNoticeModal.tsx"
Cohesion: 0.22
Nodes (16): ConstraintExhaustionNoticeModal(), ConstraintExhaustionNoticeModalProps, ConstraintProposalData, DecisionInfo, parseDecision(), CANONICAL_ERAS, CANONICAL_GENRES, CANONICAL_LANGUAGES (+8 more)

### Community 22 - "WebSocketRevocationTests"
Cohesion: 0.08
Nodes (8): broadcast_credential_revocation(), WebSocketRevocationTests, run(), run(), run(), run(), run(), run()

### Community 23 - "ProposalExecutionWorker"
Cohesion: 0.08
Nodes (4): Command, ProposalExecutionWorker, ProposalOutboxWorkerTestCase, ProposalOutboxProcessBatchView

### Community 24 - "Pre1990ReleasePeriodFilterTests"
Cohesion: 0.04
Nodes (4): ClassicVaultEraFilterTests, Pre1990ReleasePeriodFilterTests, SwipeFailureRecoveryAndEdgeCaseTests, calculate_preference_score()

### Community 26 - "permissions.py"
Cohesion: 0.15
Nodes (4): configure_sqlite_pragmas(), CoreConfig, CoreConfig, IsOwner

### Community 28 - "batch3_handlers.py"
Cohesion: 0.25
Nodes (3): handle_full_reconciliation(), handle_sync_changes_feed(), to_json_safe()

### Community 29 - "Root Cause Tracing Techniques"
Cohesion: 0.07
Nodes (26): Checkpoint: When investigation is complete, Common Root Cause Patterns, Component Boundary Tracing, Configuration mismatch, Data Flow Analysis, Diff-based investigation, Error Message Anatomy, Example: Wrong calculation (+18 more)

### Community 30 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 31 - "TMDBRateLimiterInMemoryTests"
Cohesion: 0.09
Nodes (3): acquire_tmdb_token(), reset_rate_limiter(), TMDBRateLimiterInMemoryTests

### Community 33 - "Systematic Debugging"
Cohesion: 0.12
Nodes (15): Do not use this skill when, Examples, First move, Guardrails, Inputs to gather, Outputs, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis (+7 more)

### Community 34 - "manifest.json"
Cohesion: 0.12
Nodes (16): background_color, categories, description, display, icons, lang, name, orientation (+8 more)

### Community 37 - "CollaborativeAgreement"
Cohesion: 0.05
Nodes (15): CollaborativeAgreement, SessionStats, ConflictingResponseError, DeckAdvancementService, DeckStateError, InvalidCardIndexError, OutOfOrderResponseError, StaleManifestError (+7 more)

### Community 38 - "evaluate_eligibility_predicates"
Cohesion: 0.06
Nodes (7): validate_movie_language(), MovieQuerySet, evaluate_eligibility_predicates(), EligibilityPredicatesOptionBTests, LanguageValidationTests, MovieEligibilityModelAndSignalTests, MovieQuerySetRestrictionTests

### Community 40 - "backend/package.json"
Cohesion: 0.36
Nodes (7): devDependencies, autoprefixer@^10.4.23, postcss@^8.5.6, tailwindcss@^4.1.18, tailwindcss, autoprefixer, postcss

### Community 41 - "handle_catalogue_classification"
Cohesion: 0.25
Nodes (5): acquire_tmdb_token(), handle_catalogue_classification(), handle_catalogue_enrichment(), record_tmdb_429(), _tmdb_api_get()

### Community 47 - "Session"
Cohesion: 0.03
Nodes (33): Session, DeleteAccountView, GenreListView, GenreSyncTMDBView, GuestConvertView, GuestProvisionView, GuestRecoverView, GuestRecoveryAckView (+25 more)

### Community 49 - "CatalogueJob"
Cohesion: 0.04
Nodes (23): Command, _build_candidate_queryset(), CatalogueJob, JobType, Meta, Status, movie_genres_changed_handler(), recalculate_movie_eligibility() (+15 more)

### Community 50 - ".agent/skills/ui-ux-pro-max/scripts/design_system.py"
Cohesion: 0.14
Nodes (8): _detect_page_type(), format_ascii_box(), format_markdown(), format_master_md(), format_page_override_md(), generate_design_system(), _generate_intelligent_overrides(), persist_design_system()

### Community 54 - "scripts"
Cohesion: 0.33
Nodes (6): scripts, build, dev, lint, preview, test

### Community 55 - "6. Flick-Specific Error Handling Architecture"
Cohesion: 0.40
Nodes (5): 1. Custom Exception Handler (`backend/backend/exceptions.py`), 2. Secret Redaction Filter (`core/logging.py`), 3. Request Correlation ID Middleware (`core/middleware.py`), 6. Flick-Specific Error Handling Architecture, Backend Error Handling (DRF, Exceptions & Middleware)

### Community 56 - "5xx — Server-Side & Upstream Errors"
Cohesion: 0.40
Nodes (5): 5xx — Server-Side & Upstream Errors, HTTP 500 Internal Server Error, HTTP 502 Bad Gateway, HTTP 503 Service Unavailable, HTTP 504 Gateway Timeout

### Community 57 - "React + TypeScript + Vite"
Cohesion: 0.50
Nodes (3): Expanding the ESLint configuration, React Compiler, React + TypeScript + Vite

### Community 58 - "vercel.json"
Cohesion: 0.50
Nodes (3): cleanUrls, rewrites, $schema

### Community 59 - "tmdb.py"
Cohesion: 0.06
Nodes (33): discover_movies(), _fetch(), fetch_cached_tmdb(), format_tmdb_movie(), get_enhanced_movie_details(), get_genres_map(), get_movie_by_tmdb_id(), _fetch() (+25 more)

### Community 62 - "tmdb.py"
Cohesion: 0.15
Nodes (9): calculate_cooldown_with_jitter(), get_rate_limiter_status(), get_redis_client(), is_production(), record_tmdb_429(), _redis_eval_acquire(), _redis_eval_record_429(), _redis_eval_status() (+1 more)

### Community 64 - "ConstraintExpansionProposal"
Cohesion: 0.13
Nodes (5): ConstraintExpansionProposal, Meta, ConstraintExpansionProposalSerializer, Meta, ProposalListCreateView

### Community 65 - "test_proposals.py"
Cohesion: 0.19
Nodes (10): ProposalError, ProposalExpiredError, ProposalInvalidStateError, ProposalNotFoundError, ProposalPermissionDeniedError, ProposalSupersededError, ProposalApproveView, ProposalDecideView (+2 more)

### Community 71 - "InteractionLog"
Cohesion: 0.05
Nodes (18): InteractionLog, Meta, MovieTag, compute_cohort_divergence(), compute_negative_response_rate(), compute_preference_alignment(), compute_shelf_diversity(), compute_unexposed_discovery_ratio() (+10 more)

### Community 72 - ".agent/skills/ui-ux-pro-max/scripts/core.py"
Cohesion: 0.06
Nodes (12): BM25, detect_domain(), _load_csv(), search(), _search_csv(), search_stack(), BM25, detect_domain() (+4 more)

### Community 79 - "9. Practical Troubleshooting Playbook"
Cohesion: 0.12
Nodes (17): 10. `502 Bad Gateway`, 11. `503 Service Unavailable`, 12. `504 Gateway Timeout`, 13. `ConnectionResetError(54, 'Connection reset by peer')`, 14. `ECONNREFUSED 127.0.0.1:8000`, 15. `AbortError: The operation was aborted`, 16. `CatalogueJob status = failed_permanent`, 1. `200 55` (+9 more)

### Community 80 - "admin.py"
Cohesion: 0.05
Nodes (20): CustomUserAdmin, GenreAdmin, MatchAdmin, MovieAdmin, MovieStreamingAvailabilityAdmin, SessionAdmin, SessionStatsAdmin, StreamingProviderAdmin (+12 more)

### Community 81 - "ArchiveShelvesService"
Cohesion: 0.08
Nodes (9): MovieSerializer, Meta, ArchiveShelvesService, MovieCreateView, MovieDetailView, MovieUpdateView, CompleteCatalogueView, CuratorsSelectionView (+1 more)

### Community 82 - "models.py"
Cohesion: 0.06
Nodes (21): Command, Genre, MovieManager, ProposalOutboxMessage, Meta, SessionChemistry, Meta, Swipe (+13 more)

### Community 84 - "ui-ux-pro-max"
Cohesion: 0.07
Nodes (29): Accessibility, Available Domains, Available Stacks, Common Rules for Professional UI, Example Workflow, How to Use This Skill, Icons & Visual Elements, Interaction (+21 more)

### Community 86 - "api.ts"
Cohesion: 0.08
Nodes (43): 2. Automatic Error Message Extraction, AuthShell(), generateUsernameSuggestions(), getPasswordStrength(), STEPS, RecoveryCodeModal(), RecoveryCodeModalProps, acknowledgeRecovery() (+35 more)

### Community 88 - "HardConstraints"
Cohesion: 0.07
Nodes (6): ManifestCompilerService, CandidatePool, HardConstraints, ManifestLearnedFeedbackIntegrationTests, ReproducibilityAndPersistenceTests, Phase6BatchBConcurrencyTests

### Community 92 - "ui-ux-pro-max"
Cohesion: 0.07
Nodes (29): Accessibility, Available Domains, Available Stacks, Common Rules for Professional UI, Example Workflow, How to Use This Skill, Icons & Visual Elements, Interaction (+21 more)

### Community 93 - ".agents/skills/ui-ux-pro-max/scripts/design_system.py"
Cohesion: 0.14
Nodes (8): _detect_page_type(), format_ascii_box(), format_markdown(), format_master_md(), format_page_override_md(), generate_design_system(), _generate_intelligent_overrides(), persist_design_system()

### Community 96 - "set_redis_client"
Cohesion: 0.11
Nodes (3): set_redis_client(), TMDBRateLimiterProductionFailClosedTests, TMDBRateLimiterRedisLuaMockTests

### Community 99 - ".agent/skills/ui-ux-pro-max/scripts/search.py"
Cohesion: 0.11
Nodes (4): format_output(), format_output(), main(), start.sh script

### Community 107 - ".calculate_allocation"
Cohesion: 0.10
Nodes (3): HamiltonManifestAllocatorTests, NormalManifestCompilationTests, ShortageRedistributionAndFloorTests

### Community 109 - "Phase6BatchCTMDBReliabilityTests"
Cohesion: 0.14
Nodes (5): _create_tmdb_session(), get_tmdb_session(), reset_tmdb_session(), Phase6BatchCTMDBReliabilityTests, worker()

### Community 111 - ".record_swipe_response"
Cohesion: 0.04
Nodes (5): submit_duplicate(), submit_guest(), submit_host(), submit_swipe(), SuperLikeReactionMatrixIntegrationTests

### Community 114 - "SessionPage.tsx"
Cohesion: 0.05
Nodes (38): ErrorBoundary, Props, State, activeSessionSockets, cardVariants, Match, Movie, MovieSwipeCard (+30 more)

### Community 115 - "Workflow Phases (Summary)"
Cohesion: 0.25
Nodes (7): Common Rationalisations, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis, Phase 3: Hypothesis and Testing, Phase 4: Implementation, Phases, Red Flags, and Common Rationalisations, Workflow Phases (Summary)

### Community 117 - "UserPreferenceData"
Cohesion: 0.04
Nodes (7): normalize_user_preferences(), CollaborativeDeckScorer, MovieIntelligenceData, UserPreferenceData, RoomRecommendationScenariosTestCase, ScoringServiceTestCase, Stage3EndToEndProductValidationTests

### Community 129 - "tests.py"
Cohesion: 0.03
Nodes (12): AuthenticationThrottlingTests, ConcurrencyAndAtomicityTests, DiscoverTests, EmailVerificationTests, GenreIntegrationTests, LocalNetworkConfigurationTests, RecentSessionsTests, RecommendationDiscoveryTests (+4 more)

### Community 136 - "eslint.config.js"
Cohesion: 0.15
Nodes (12): eslint@^9.39.1, @eslint/js@^9.39.1, eslint-plugin-react-hooks@^7.0.1, eslint-plugin-react-refresh@^0.4.24, globals@^16.5.0, typescript-eslint@^8.46.4, eslint, @eslint/js (+4 more)

### Community 137 - "interface"
Cohesion: 0.33
Nodes (5): interface, display_name, short_description, policy, allow_implicit_invocation

### Community 138 - ".authenticate"
Cohesion: 0.11
Nodes (3): EmailOrUsernameModelBackend, AuthenticationLoggingSecurityTests, LoginView

### Community 139 - "Examples"
Cohesion: 0.40
Nodes (4): Example 1: Test failure with stack trace, Example 2: Intermittent test failure, Example 3: Regression after a commit, Examples

### Community 144 - "HomePage.tsx"
Cohesion: 0.07
Nodes (26): dependencies, canvas-confetti@^1.9.4, framer-motion@^12.31.0, posthog-js@^1.319.0, react@^19.2.0, react-dom@^19.2.0, react-router-dom@^7.12.0, backdropVariants (+18 more)

### Community 147 - "devDependencies"
Cohesion: 0.15
Nodes (13): devDependencies, jsdom@^30.1.3, @testing-library/react@^16.3.3, @types/canvas-confetti@^1.9.0, @types/react@^19.2.5, @types/react-dom@^19.2.3, typescript@~5.9.3, vitest@^5.1.0 (+5 more)

### Community 150 - "views.py"
Cohesion: 0.04
Nodes (19): MovieTagRelation, Meta, StandardResultsSetPagination, SwipeHistoryPagination, RegisterSerializer, Meta, SwipeSerializer, Meta (+11 more)

### Community 167 - "4xx — Client-Side Errors"
Cohesion: 0.18
Nodes (11): 4xx — Client-Side Errors, HTTP 400 Bad Request, HTTP 401 Unauthorized, HTTP 403 Forbidden, HTTP 404 Not Found, HTTP 405 Method Not Allowed, HTTP 408 Request Timeout, HTTP 409 Conflict (+3 more)

### Community 171 - "flick-frontend/package.json"
Cohesion: 0.15
Nodes (12): lucide-react@^0.577.0, material-symbols@^0.40.2, tailwindcss@^4.1.18, @types/node@^24.10.1, tailwindcss, name, private, type (+4 more)

### Community 177 - "_assert_safe_local_database"
Cohesion: 0.21
Nodes (5): _assert_safe_local_database(), _resolve_canonical_db_path(), SafetyGuardDebugFalseTest, SafetyGuardEngineTest, SafetyGuardPathTest

### Community 178 - "Flick — HTTP Status Codes, Server Logs & Error-Handling Reference"
Cohesion: 0.13
Nodes (14): 10. Glossary of Key Technical Terms, 1. Quick-Reference Cheat Sheet, 2. What Are HTTP Status Codes?, 7. Background Queue & Worker Numbers, 8. Frontend & Build-Related Numbers, At a Glance: What Do These Numbers Mean?, Flick — HTTP Status Codes, Server Logs & Error-Handling Reference, Port Numbers (+6 more)

### Community 179 - "CorrectSyntheticM1RecordsTest"
Cohesion: 0.18
Nodes (3): _resolve_staff_user(), CorrectSyntheticM1RecordsTest, _guard_pass()

### Community 180 - "verify-batch-b-browser.js"
Cohesion: 0.21
Nodes (5): puppeteer-core@^25.16.0, SCREENSHOT_DIR, SCREENSHOT_DIR, SCREENSHOT_DIR, puppeteer-core

### Community 184 - "2xx — Successful Responses"
Cohesion: 0.20
Nodes (10): 2xx — Successful Responses, 3. Complete HTTP Status Code Guide, 3xx — Redirection & Caching, HTTP 200 OK, HTTP 201 Created, HTTP 202 Accepted, HTTP 204 No Content, HTTP 301 Moved Permanently (+2 more)

### Community 186 - "vite.config.ts"
Cohesion: 0.22
Nodes (6): @tailwindcss/vite@^4.1.18, vite@^7.2.4, @vitejs/plugin-react@^5.1.1, @tailwindcss/vite, vite, @vitejs/plugin-react

### Community 190 - "IntelligenceWorkerProcess"
Cohesion: 0.08
Nodes (3): Command, IntelligenceWorkerProcess, register_handler()

### Community 191 - "CatalogueQueueService"
Cohesion: 0.09
Nodes (11): Command, TmdbChangesCheckpoint, Meta, CatalogueQueueService, PollerLockedError, RateLimitBackoffError, StalePollerOwnershipError, TmdbChangesService (+3 more)

### Community 192 - "WatchlistItem"
Cohesion: 0.10
Nodes (5): WatchlistItem, Meta, PaginationAndResourceLimitTests, WatchlistTests, WatchlistDetailView

### Community 197 - "5. Deep Dive: HTTP 304 Not Modified & Caching"
Cohesion: 0.40
Nodes (5): 5. Deep Dive: HTTP 304 Not Modified & Caching, Conditional Requests (ETag & Last-Modified), How Browser Caching Works, How Caching Is Implemented in Flick, When 304 Is Healthy vs When It Is a Problem

### Community 201 - "HistoricalReconciliationService"
Cohesion: 0.09
Nodes (12): HistoricalReconciliationService, map_swipe_reaction(), reconcile_historical_interactions(), HistoricalReconciliationServiceTests, Task 3: Historical Interaction Reconciliation Service & Command, Batch 4: Historical Interaction Reconciliation & Identity Linking — Task List, Checkpoint 1: Foundations Complete, Checkpoint 2: Reconciliation & Identity Complete (+4 more)

### Community 202 - "PostgreSQLQueueConcurrencyTests"
Cohesion: 0.12
Nodes (3): PostgreSQLQueueConcurrencyTests, do_enqueue(), worker_task()

### Community 204 - "4. Deciphering Server Logs & Trailing Numbers"
Cohesion: 0.29
Nodes (7): 4. Deciphering Server Logs & Trailing Numbers, Anatomy of a Django/Daphne Access Log, What Do the Trailing Numbers Mean? (The 55 vs 1989 Mystery), Why does `/api/curators-selection/` show `200 1989`?, Why does `/api/users/profile/` show `200 55`?, Why does `GET /api/movies/` show `304 -` or `304 0`?, WSGI vs ASGI Logging Differences

### Community 211 - "InMemoryTokenBucket"
Cohesion: 0.15
Nodes (5): InMemoryTokenBucket, 1. The Movie Database (TMDB), 2. Redis, 3. PostgreSQL & SQLite, External Service Failure Modes (TMDB, Redis, Postgres)

### Community 219 - "test_observability_and_security.py"
Cohesion: 0.07
Nodes (5): CorrelationIdFilter, SecretRedactionFilter, SecretRedactionLoggerTests, DiscoverView, normalize_pair()

### Community 239 - "UserTasteProfile"
Cohesion: 0.04
Nodes (24): MovieKeyword, UserIdentityLink, LinkType, Meta, UserProfile, UserTasteProfile, DuplicateIdentityLinkError, IdentityLinkingService (+16 more)

### Community 244 - "run_staleness_sweep"
Cohesion: 0.07
Nodes (5): Command, StalenessSweepCheckpoint, Meta, run_staleness_sweep(), StalenessSweepTests

### Community 248 - "Match"
Cohesion: 0.10
Nodes (5): Match, Meta, SessionHistoryTests, compute_session_statistics(), serialize_session_matches()

### Community 260 - "retrieval.py"
Cohesion: 0.07
Nodes (18): SessionOccasionState, ActiveManifestImmutableError, HamiltonManifestAllocator, InsufficientCandidatesError, ManifestCompilationError, ReplenishmentInProgressError, ScoredCandidate, TransientReplenishmentError (+10 more)

## Knowledge Gaps
- **99 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Movie` connect `Movie` to `HardConstraintFilter`, `Phase6BatchBBackendTests`, `tests.py`, `retrieval.py`, `_make_movie`, `LimitValidationTest`, `ProposalLifecycleAndIdempotencyTestCase`, `Batch3WorkerIntegrationTests`, `SwipeAndMatchingTests`, `Batch5PersonalizationEvaluationTests`, `DeckStateAPITests`, `DynamicMovieCatalogueTests`, `views.py`, `ProposalExecutionWorker`, `Pre1990ReleasePeriodFilterTests`, `SessionLifecycleAndQuestionnaireRecoveryTests`, `transition_movie_classification`, `MatchListFilteringSecurityTests`, `AffinityEvaluationTests`, `CollaborativeAgreement`, `evaluate_eligibility_predicates`, `SwipeUndoTests`, `handle_catalogue_classification`, `ScreeningSessionResultsAndStatsPersistenceTests`, `Session`, `CatalogueJob`, `SwipeUndoViewInverseParityTests`, `CorrectSyntheticM1RecordsTest`, `tmdb.py`, `LocalizedGenreRetrievalTests`, `CatalogueQueueService`, `WatchlistItem`, `test_proposals.py`, `InteractionLog`, `.handle`, `HistoricalReconciliationService`, `PostgreSQLQueueConcurrencyTests`, `.handle`, `TestIndianLanguageDiscovery`, `._record_interactions`, `admin.py`, `ArchiveShelvesService`, `models.py`, `IntelligenceModelsTestCase`, `StreamingOptionsRemediationTests`, `HardConstraints`, `test_observability_and_security.py`, `enrichment_handlers.py`, `InteractionLogProcessingStatusTests`, `Phase1EndToEndScenarioTestCase`, `_validate_candidate`, `AuthenticationAndPermissionTests`, `BoutiqueManifestCompilationTests`, `.calculate_allocation`, `SuperLikePersistenceAndAttributionTests`, `UserTasteProfile`, `.record_swipe_response`, `DatabaseConcurrencyAndSwipeReliabilityTests`, `run_staleness_sweep`, `UserPreferenceData`, `TestIngestionAndProvenance`, `MotionAndSessionRegressionAuditTests`, `Match`, `CoreUserExperienceRepairTests`, `FunctionalAndMobileAuditVerificationTests`, `CandidateRetrievalAndEligibilityTests`, `TestReliabilityAndRetrieval`?**
  _High betweenness centrality (0.267) - this node is a cross-community bridge._
- **Are the 128 inferred relationships involving `Movie` (e.g. with `Command` and `Command`) actually correct?**
  _`Movie` has 128 INFERRED edges - model-reasoned connections that need verification._
- **Should `HardConstraintFilter` be split into smaller, more focused modules?**
  _Cohesion score 0.06565656565656566 - nodes in this community are weakly interconnected._
- **Why does `6. Flick-Specific Error Handling Architecture` connect `6. Flick-Specific Error Handling Architecture` to `Flick — HTTP Status Codes, Server Logs & Error-Handling Reference`, `apiRequest`, `InMemoryTokenBucket`?**
  _High betweenness centrality (0.172) - this node is a cross-community bridge._
- **Are the 78 inferred relationships involving `Session` (e.g. with `MatchConsumer` and `SessionDetailSerializer`) actually correct?**
  _`Session` has 78 INFERRED edges - model-reasoned connections that need verification._
- **Should `Defense-in-Depth Debugging Strategies` be split into smaller, more focused modules?**
  _Cohesion score 0.06451612903225806 - nodes in this community are weakly interconnected._
- **Why does `Frontend Error Handling (`api.ts` & React)` connect `apiRequest` to `api.ts`, `6. Flick-Specific Error Handling Architecture`?**
  _High betweenness centrality (0.171) - this node is a cross-community bridge._