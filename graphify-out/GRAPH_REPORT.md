# Graph Report - flick-app  (2026-11-17)

## Corpus Check
- 247 files · ~373,916 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 59 file(s) not represented in the graph (top: .csv 48, (none) 7, .example 2)

## Summary
- 4248 nodes · 9196 edges · 190 communities (100 shown, 90 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 1049 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `22fdcbb0`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- HardConstraintFilter
- Defense-in-Depth Debugging Strategies
- canonicalize_recovery_code
- django_db
- _make_movie
- router.tsx
- GuestConversionValidationAndRejectionTests
- WebSocketAuthenticationAndAuthorizationTests
- DiscoverPage.tsx
- apiRequest
- handle_catalogue_classification
- SessionPage.tsx
- Batch3WorkerIntegrationTests
- CinemaHeader
- MovieSerializer
- Batch5PersonalizationEvaluationTests
- DynamicMovieCatalogueTests
- test_observability_and_security.py
- HomePage.tsx
- compilerOptions
- ConstraintExhaustionNoticeModal.tsx
- Stage3EndToEndProductValidationTests
- WebSocketRevocationTests
- ProposalExecutionWorker
- Pre1990ReleasePeriodFilterTests
- SessionLifecycleAndQuestionnaireRecoveryTests
- permissions.py
- test_seed_local_dev_catalogue.py
- CatalogueJob
- Root Cause Tracing Techniques
- compilerOptions
- TMDBRateLimiterInMemoryTests
- MatchConsumer
- Systematic Debugging
- manifest.json
- ProposalAPITestCase
- IntelligenceWorkerProcess
- RecommendationDiscoveryTests
- evaluate_eligibility_predicates
- ProfilePage.tsx
- backend/package.json
- test_recommendation_evaluation.py
- .record_swipe_response
- SwipeUndoView
- admin.py
- ScreeningSessionResultsAndStatsPersistenceTests
- DesignSystemGenerator
- views.py
- .link_guest_to_user
- _ingest_tmdb_results
- .agent/skills/ui-ux-pro-max/scripts/design_system.py
- TestCase
- DesignSystemGenerator
- guest_security.py
- scripts
- 6. Flick-Specific Error Handling Architecture
- 3. Complete HTTP Status Code Guide
- React + TypeScript + Vite
- vercel.json
- tmdb.py
- .enqueue
- StreamingProvider
- tmdb.py
- sw.js
- ConstraintExpansionProposal
- test_proposals.py
- tsconfig.json
- retrieval.py
- GuestActivityTrackingTests
- Phase6BatchCRecentSessionsAndStreamingTests
- _get_tmdb_request_headers
- Swipe
- .agent/skills/ui-ux-pro-max/scripts/core.py
- MovieTagRelation
- 9. Practical Troubleshooting Playbook
- batch_sync_prelaunch.py
- ArchiveShelvesService
- Genre
- TmdbChangesServiceTests
- ui-ux-pro-max
- .anonymize_and_delete_user
- api.ts
- UserIdentityLinkModelTests
- HardConstraints
- GuestSecurityHMACAndVerificationTests
- ClassicVaultEraFilterTests
- PostgreSQLQueueConcurrencyTests
- ui-ux-pro-max
- .agents/skills/ui-ux-pro-max/scripts/design_system.py
- PreferenceAndManifestCorrectnessTests
- .recompute_user_taste_profile
- set_redis_client
- TestReliabilityAndRetrieval
- AuthenticationAndPermissionTests
- .agent/skills/ui-ux-pro-max/scripts/search.py
- AuthenticationThrottlingTests
- TmdbChangesService
- StreamingFilterAuditTests
- GuestProfile
- UniversalLocalNetworkDevConfigurationTests
- 7. Background Queue & Worker Numbers
- .calculate_allocation
- GuestRecoveryAPITests
- Phase6BatchCTMDBReliabilityTests
- SessionDetailSerializer
- Session
- SuperLikeReactionMatrixIntegrationTests
- AdminCommandSecurityTests
- SessionPage.tsx
- Workflow Phases (Summary)
- SessionJoiningTests
- UserPreferenceData
- TmdbChangesCheckpoint
- SettingsSecurityTests
- RecoveryHandoffReliabilityTests
- GuestProfileModelTests
- StreamingOptionsRemediationTests
- FunctionalAndMobileAuditVerificationTests
- diagnose_lan_connectivity.sh
- CandidateRetrievalAndEligibilityTests
- CoreUserExperienceRepairTests
- HealthCheckView
- Phase6BatchBBackendTests
- Swipe
- middleware.py
- SessionCodeCollisionTests
- MovieListView
- GuestRecoveryConcurrencyTests
- PaginationAndResourceLimitTests
- eslint.config.js
- interface
- PasswordResetSecurityTests
- Examples
- SwipeSerializer
- EmailVerificationTests
- dependencies
- WatchlistTests
- compute_session_statistics
- devDependencies
- Command
- Command
- AuthRateThrottle
- GuestActivityMiddleware
- handle_recompute_taste_profile
- LocalNetworkConfigurationTests
- SessionQueryOptimizationTests
- calculate_entropy_bits
- .test_concurrent_duplicate_submissions_by_single_user
- .test_concurrent_duplicate_submissions_race_condition
- MatchListFilteringSecurityTests
- GuestConversionConcurrencyTests
- 4xx — Client-Side Errors
- flick-frontend/package.json
- Flick — HTTP Status Codes, Server Logs & Error-Handling Reference
- CorrectSyntheticM1RecordsTest
- verify-batch-b-browser.js
- 2xx — Successful Responses
- vite.config.ts
- tmdb_changes.py
- WatchlistItem
- parse_retry_after
- 5. Deep Dive: HTTP 304 Not Modified & Caching
- GuestProvisioningAPITests
- .link_guest_to_user
- 4. Deciphering Server Logs & Trailing Numbers
- TestIndianLanguageDiscovery
- IntelligenceModelsTestCase
- InMemoryTokenBucket
- SecretRedactionFilter
- BoutiqueManifestCompilationTests
- SuperLikePersistenceAndAttributionTests
- DatabaseConcurrencyAndSwipeReliabilityTests
- run_staleness_sweep
- MotionAndSessionRegressionAuditTests
- SessionHistoryTests
- ShortageRedistributionAndFloorTests
- Command
- DeckStateAPITests

## God Nodes (most connected - your core abstractions)
1. `Movie` - 209 edges
2. `Session` - 128 edges
3. `Genre` - 96 edges
4. `apiRequest()` - 75 edges
5. `UserPreferenceData` - 74 edges
6. `Swipe` - 71 edges
7. `HardConstraints` - 66 edges
8. `CollaborativeAgreement` - 60 edges
9. `InteractionLog` - 60 edges
10. `CatalogueJob` - 52 edges

## Surprising Connections (you probably didn't know these)
- `2. Secret Redaction Filter (`core/logging.py`)` --references--> `SecretRedactionFilter`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/logging.py
- `Anatomy of a Django/Daphne Access Log` --references--> `CorrelationIdMiddleware`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/middleware.py
- `Architecture & Data Decisions` --references--> `InteractionLog`  [INFERRED]
  tasks/plan.md → backend/core/models.py
- `Worker Leases, Fencing Tokens & Heartbeats` --references--> `StaleLeaseOwnershipError`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/services/catalogue_queue.py
- `Task 4: Guest Identity Linking Service` --references--> `IdentityLinkingService`  [INFERRED]
  tasks/plan.md → backend/core/services/identity_linking.py

## Import Cycles
- None detected.

## Communities (190 total, 90 thin omitted)

### Community 1 - "Defense-in-Depth Debugging Strategies"
Cohesion: 0.06
Nodes (30): Boundary Testing, Checkpoint: Layered debugging complete, Cleanup and teardown, Defense-in-Depth Debugging Strategies, Dependency isolation, Divide and Conquer, Hypothesis Testing Protocol, Input validation (+22 more)

### Community 3 - "django_db"
Cohesion: 0.03
Nodes (39): Migration, Migration, Migration, Migration, Migration, Migration, Migration, Migration (+31 more)

### Community 4 - "_make_movie"
Cohesion: 0.07
Nodes (11): _assert_safe_local_database(), _resolve_canonical_db_path(), DryRunImmutabilityTest, _guard_pass(), LimitValidationTest, _make_movie(), _mock_tmdb_response(), SafetyGuardDebugFalseTest (+3 more)

### Community 5 - "router.tsx"
Cohesion: 0.13
Nodes (25): AccountSettingsPage, AnimatedRoutes(), AutoJoin, CreateSessionPage, DiscoverPage, EntryPage, ForgotPasswordPage, GuestConvertPage (+17 more)

### Community 6 - "GuestConversionValidationAndRejectionTests"
Cohesion: 0.07
Nodes (3): GuestConversionRecoverySecurityTests, GuestConversionSuccessTests, GuestConversionValidationAndRejectionTests

### Community 8 - "DiscoverPage.tsx"
Cohesion: 0.06
Nodes (31): Provider, ProviderLogo(), streamingCache, StreamingData, StreamingOptions(), ArchiveShelf, ArchiveShelfSection(), CatalogueSort (+23 more)

### Community 9 - "apiRequest"
Cohesion: 0.12
Nodes (29): 1. The `ApiError` Class, 2. Automatic Error Message Extraction, 3. Automatic Session Expiration Handling (401 Interceptor), 4. Empty States vs. Actual Errors, Frontend Error Handling (`api.ts` & React), AuthShell(), generateUsernameSuggestions(), getPasswordStrength() (+21 more)

### Community 10 - "handle_catalogue_classification"
Cohesion: 0.08
Nodes (7): acquire_tmdb_token(), handle_catalogue_classification(), handle_catalogue_enrichment(), is_synthetic_movie(), record_tmdb_429(), _tmdb_api_get(), Batch2EnrichmentAndWorkerTests

### Community 11 - "SessionPage.tsx"
Cohesion: 0.07
Nodes (42): DeckCardSkeleton(), MatchItemSkeleton(), MovieCardSkeleton(), ShelfSkeleton(), Skeleton(), SkeletonProps, StreamingItemSkeleton(), getWsBaseUrl() (+34 more)

### Community 12 - "Batch3WorkerIntegrationTests"
Cohesion: 0.08
Nodes (3): _beat(), reset_handlers(), Batch3WorkerIntegrationTests

### Community 13 - "CinemaHeader"
Cohesion: 0.13
Nodes (25): BottomNav(), BottomNavProps, NavTab, CinemaHeader(), CinemaHeaderProps, AccountSettingsPage(), handleChangeEmail(), handleChangePassword() (+17 more)

### Community 14 - "MovieSerializer"
Cohesion: 0.09
Nodes (10): SessionChemistry, Meta, MovieSerializer, Meta, calculate_preference_score(), MovieCreateView, MovieDetailView, normalize_pair() (+2 more)

### Community 15 - "Batch5PersonalizationEvaluationTests"
Cohesion: 0.05
Nodes (4): _movie_get(), _movie_getitem(), _pluralize_genre(), Batch5PersonalizationEvaluationTests

### Community 17 - "test_observability_and_security.py"
Cohesion: 0.06
Nodes (12): get_correlation_id(), reset_correlation_id(), set_correlation_id(), CorrelationIdMiddleware, CorrelationIdConcurrencyTests, run_all(), worker(), async_view() (+4 more)

### Community 18 - "HomePage.tsx"
Cohesion: 0.06
Nodes (35): posthog-js@^1.319.0, trackEvent(), CreateSessionPage(), createSession(), Genre, getGenreIcon(), Industry, INDUSTRY_OPTIONS (+27 more)

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
Cohesion: 0.06
Nodes (9): Command, ProposalOutboxMessage, Meta, ProposalOutboxMessageSerializer, Meta, ProposalExecutionWorker, ProposalLifecycleAndIdempotencyTestCase, ProposalOutboxWorkerTestCase (+1 more)

### Community 26 - "permissions.py"
Cohesion: 0.15
Nodes (4): configure_sqlite_pragmas(), CoreConfig, CoreConfig, IsOwner

### Community 27 - "test_seed_local_dev_catalogue.py"
Cohesion: 0.04
Nodes (13): Command, Movie, movie_genres_changed_handler(), recalculate_movie_eligibility(), register_eligibility_signals(), check_deterministic_identity(), normalize_title(), transition_movie_classification() (+5 more)

### Community 28 - "CatalogueJob"
Cohesion: 0.10
Nodes (10): CatalogueJob, JobType, Meta, Status, handle_full_reconciliation(), handle_sync_changes_feed(), to_json_safe(), CatalogueQueueError (+2 more)

### Community 29 - "Root Cause Tracing Techniques"
Cohesion: 0.07
Nodes (26): Checkpoint: When investigation is complete, Common Root Cause Patterns, Component Boundary Tracing, Configuration mismatch, Data Flow Analysis, Diff-based investigation, Error Message Anatomy, Example: Wrong calculation (+18 more)

### Community 30 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 33 - "Systematic Debugging"
Cohesion: 0.12
Nodes (15): Do not use this skill when, Examples, First move, Guardrails, Inputs to gather, Outputs, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis (+7 more)

### Community 34 - "manifest.json"
Cohesion: 0.12
Nodes (16): background_color, categories, description, display, icons, lang, name, orientation (+8 more)

### Community 36 - "IntelligenceWorkerProcess"
Cohesion: 0.08
Nodes (3): Command, IntelligenceWorkerProcess, register_handler()

### Community 38 - "evaluate_eligibility_predicates"
Cohesion: 0.06
Nodes (7): validate_movie_language(), MovieQuerySet, evaluate_eligibility_predicates(), EligibilityPredicatesOptionBTests, LanguageValidationTests, MovieEligibilityModelAndSignalTests, MovieQuerySetRestrictionTests

### Community 39 - "ProfilePage.tsx"
Cohesion: 0.14
Nodes (16): App(), AppRouter(), RouteLoadingFallback(), CinematicLoader(), CinematicLoaderProps, FLICK_LOGOS, Theme, ThemeContext (+8 more)

### Community 40 - "backend/package.json"
Cohesion: 0.36
Nodes (7): devDependencies, autoprefixer@^10.4.23, postcss@^8.5.6, tailwindcss@^4.1.18, tailwindcss, autoprefixer, postcss

### Community 41 - "test_recommendation_evaluation.py"
Cohesion: 0.07
Nodes (10): compute_cohort_divergence(), compute_negative_response_rate(), compute_preference_alignment(), compute_shelf_diversity(), compute_unexposed_discovery_ratio(), _extract_movie_id(), _extract_movie_tokens(), RecommendationEvaluationService (+2 more)

### Community 43 - "SwipeUndoView"
Cohesion: 0.09
Nodes (19): UserTasteSignal, Meta, SwipeUndoView, _update_analytics_after_commit(), Architecture & Data Decisions, Detailed Tasks, Implementation Plan: Batch 4 — Historical Interaction Reconciliation and Identity Linking, Overview (+11 more)

### Community 44 - "admin.py"
Cohesion: 0.20
Nodes (11): CustomUserAdmin, GenreAdmin, MatchAdmin, MovieAdmin, MovieStreamingAvailabilityAdmin, SessionAdmin, SessionStatsAdmin, StreamingProviderAdmin (+3 more)

### Community 47 - "views.py"
Cohesion: 0.04
Nodes (31): DeckSwipeUndoView, DeleteAccountView, ensure_default_genres(), GenreListView, GenreSyncTMDBView, GuestConvertView, GuestProvisionView, GuestRecoverView (+23 more)

### Community 50 - ".agent/skills/ui-ux-pro-max/scripts/design_system.py"
Cohesion: 0.14
Nodes (8): _detect_page_type(), format_ascii_box(), format_markdown(), format_master_md(), format_page_override_md(), generate_design_system(), _generate_intelligent_overrides(), persist_design_system()

### Community 51 - "TestCase"
Cohesion: 0.09
Nodes (4): DiscoverTests, GenreIntegrationTests, RecentSessionsTests, SessionLifecycleTests

### Community 53 - "guest_security.py"
Cohesion: 0.12
Nodes (6): compute_recovery_lookup_digest(), dummy_verify_recovery_code(), generate_recovery_code(), get_recovery_hmac_key(), hash_recovery_code(), verify_recovery_code()

### Community 54 - "scripts"
Cohesion: 0.33
Nodes (6): scripts, build, dev, lint, preview, test

### Community 55 - "6. Flick-Specific Error Handling Architecture"
Cohesion: 0.40
Nodes (5): 1. Custom Exception Handler (`backend/backend/exceptions.py`), 2. Secret Redaction Filter (`core/logging.py`), 3. Request Correlation ID Middleware (`core/middleware.py`), 6. Flick-Specific Error Handling Architecture, Backend Error Handling (DRF, Exceptions & Middleware)

### Community 56 - "3. Complete HTTP Status Code Guide"
Cohesion: 0.20
Nodes (10): 3. Complete HTTP Status Code Guide, 3xx — Redirection & Caching, 5xx — Server-Side & Upstream Errors, HTTP 301 Moved Permanently, HTTP 302 Found / Temporary Redirect, HTTP 304 Not Modified, HTTP 500 Internal Server Error, HTTP 502 Bad Gateway (+2 more)

### Community 57 - "React + TypeScript + Vite"
Cohesion: 0.50
Nodes (3): Expanding the ESLint configuration, React Compiler, React + TypeScript + Vite

### Community 58 - "vercel.json"
Cohesion: 0.50
Nodes (3): cleanUrls, rewrites, $schema

### Community 59 - "tmdb.py"
Cohesion: 0.07
Nodes (23): discover_movies(), fetch_cached_tmdb(), format_tmdb_movie(), get_enhanced_movie_details(), get_movie_by_tmdb_id(), get_movie_genres(), get_movie_trailer_key(), get_movie_watch_providers() (+15 more)

### Community 61 - "StreamingProvider"
Cohesion: 0.17
Nodes (7): Command, Command, MovieStreamingAvailability, Meta, StreamingProvider, _link_streaming_availability(), resolve_streaming_provider_ids()

### Community 62 - "tmdb.py"
Cohesion: 0.14
Nodes (8): get_rate_limiter_status(), get_redis_client(), is_production(), record_tmdb_429(), _redis_eval_acquire(), _redis_eval_record_429(), _redis_eval_status(), RedisRateLimiterUnavailableError

### Community 64 - "ConstraintExpansionProposal"
Cohesion: 0.17
Nodes (4): ConstraintExpansionProposalSerializer, Meta, ProposalDetailView, ProposalListCreateView

### Community 65 - "test_proposals.py"
Cohesion: 0.07
Nodes (11): ConstraintExpansionProposal, Meta, ProposalError, ProposalExpiredError, ProposalInvalidStateError, ProposalNotFoundError, ProposalPermissionDeniedError, ProposalService (+3 more)

### Community 67 - "retrieval.py"
Cohesion: 0.04
Nodes (17): calculate_questionnaire_similarity(), calculate_screening_affinity(), calculate_session_statistics(), calculate_taste_compatibility(), normalize_user_preferences(), ActiveManifestImmutableError, InsufficientCandidatesError, ManifestCompilationError (+9 more)

### Community 70 - "_get_tmdb_request_headers"
Cohesion: 0.21
Nodes (10): _fetch(), get_genres_map(), _fetch(), _fetch(), _fetch(), get_tmdb_genres(), _get_tmdb_request_headers(), _fetch() (+2 more)

### Community 71 - "Swipe"
Cohesion: 0.08
Nodes (21): InteractionLog, Meta, MovieExposure, MovieKeyword, MovieManager, MovieTag, UserIdentityLink, LinkType (+13 more)

### Community 72 - ".agent/skills/ui-ux-pro-max/scripts/core.py"
Cohesion: 0.06
Nodes (12): BM25, detect_domain(), _load_csv(), search(), _search_csv(), search_stack(), BM25, detect_domain() (+4 more)

### Community 73 - "MovieTagRelation"
Cohesion: 0.10
Nodes (6): MovieTagRelation, Meta, RegisterSerializer, Meta, generate_session_code(), SessionCreateView

### Community 79 - "9. Practical Troubleshooting Playbook"
Cohesion: 0.12
Nodes (17): 10. `502 Bad Gateway`, 11. `503 Service Unavailable`, 12. `504 Gateway Timeout`, 13. `ConnectionResetError(54, 'Connection reset by peer')`, 14. `ECONNREFUSED 127.0.0.1:8000`, 15. `AbortError: The operation was aborted`, 16. `CatalogueJob status = failed_permanent`, 1. `200 55` (+9 more)

### Community 80 - "batch_sync_prelaunch.py"
Cohesion: 0.18
Nodes (4): Command, _make_session(), _tmdb_get(), fetch_tmdb_movies()

### Community 81 - "ArchiveShelvesService"
Cohesion: 0.14
Nodes (3): ArchiveShelvesService, CuratorsSelectionView, YourArchiveView

### Community 82 - "Genre"
Cohesion: 0.18
Nodes (5): Command, Command, Genre, GenreSerializer, Meta

### Community 84 - "ui-ux-pro-max"
Cohesion: 0.07
Nodes (29): Accessibility, Available Domains, Available Stacks, Common Rules for Professional UI, Example Workflow, How to Use This Skill, Icons & Visual Elements, Interaction (+21 more)

### Community 86 - "api.ts"
Cohesion: 0.10
Nodes (30): RecoveryCodeModal(), RecoveryCodeModalProps, acknowledgeRecovery(), ApiError, buildDeduplicationKey(), clearInFlightRequests(), convertGuestAccount(), getBaseUrl (+22 more)

### Community 88 - "HardConstraints"
Cohesion: 0.04
Nodes (9): CollaborativeDeckScorer, ScoredCandidate, CandidatePool, HardConstraints, LocalizedGenreRetrievalTests, fake_ingest(), fake_ingest(), ManifestLearnedFeedbackIntegrationTests (+1 more)

### Community 91 - "PostgreSQLQueueConcurrencyTests"
Cohesion: 0.12
Nodes (3): PostgreSQLQueueConcurrencyTests, do_enqueue(), worker_task()

### Community 92 - "ui-ux-pro-max"
Cohesion: 0.07
Nodes (29): Accessibility, Available Domains, Available Stacks, Common Rules for Professional UI, Example Workflow, How to Use This Skill, Icons & Visual Elements, Interaction (+21 more)

### Community 93 - ".agents/skills/ui-ux-pro-max/scripts/design_system.py"
Cohesion: 0.14
Nodes (8): _detect_page_type(), format_ascii_box(), format_markdown(), format_master_md(), format_page_override_md(), generate_design_system(), _generate_intelligent_overrides(), persist_design_system()

### Community 96 - "set_redis_client"
Cohesion: 0.10
Nodes (4): reset_rate_limiter(), set_redis_client(), TMDBRateLimiterProductionFailClosedTests, TMDBRateLimiterRedisLuaMockTests

### Community 99 - ".agent/skills/ui-ux-pro-max/scripts/search.py"
Cohesion: 0.11
Nodes (4): format_output(), format_output(), main(), start.sh script

### Community 104 - "GuestProfile"
Cohesion: 0.15
Nodes (3): GuestProfile, Meta, GuestRecoveryAckView

### Community 106 - "7. Background Queue & Worker Numbers"
Cohesion: 0.40
Nodes (5): 7. Background Queue & Worker Numbers, Queue Priorities & Fair Scheduling Quotas, Retry Limits, Exponential Backoff & Quarantine, TMDB Dual-Bucket Rate Limiter Constants, Worker Leases, Fencing Tokens & Heartbeats

### Community 109 - "Phase6BatchCTMDBReliabilityTests"
Cohesion: 0.13
Nodes (5): _create_tmdb_session(), get_tmdb_session(), reset_tmdb_session(), Phase6BatchCTMDBReliabilityTests, worker()

### Community 111 - "Session"
Cohesion: 0.04
Nodes (21): CollaborativeAgreement, Session, SessionOccasionState, SessionSerializer, Meta, ConflictingResponseError, DeckAdvancementService, DeckStateError (+13 more)

### Community 114 - "SessionPage.tsx"
Cohesion: 0.05
Nodes (31): ErrorBoundary, Props, State, SessionPage(), AvatarStack(), RecentSession, SessionCard(), SessionsListPage() (+23 more)

### Community 115 - "Workflow Phases (Summary)"
Cohesion: 0.25
Nodes (7): Common Rationalisations, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis, Phase 3: Hypothesis and Testing, Phase 4: Implementation, Phases, Red Flags, and Common Rationalisations, Workflow Phases (Summary)

### Community 117 - "UserPreferenceData"
Cohesion: 0.04
Nodes (7): rank_candidates_for_user(), IndividualRelevanceScorer, MovieIntelligenceData, UserPreferenceData, NormalManifestCompilationTests, RoomRecommendationScenariosTestCase, ScoringServiceTestCase

### Community 118 - "TmdbChangesCheckpoint"
Cohesion: 0.18
Nodes (3): TmdbChangesCheckpoint, Meta, PollTmdbChangesCommandTests

### Community 129 - "Swipe"
Cohesion: 0.03
Nodes (15): Match, Meta, SessionStats, Swipe, Meta, DeckStateConcurrencyTests, GuestConversionDataIntegrityTests, Phase6BatchBConcurrencyTests (+7 more)

### Community 130 - "middleware.py"
Cohesion: 0.17
Nodes (3): get_user_from_token_key(), TokenAuthMiddleware, TokenAuthMiddlewareStack()

### Community 133 - "MovieListView"
Cohesion: 0.33
Nodes (3): StandardResultsSetPagination, SwipeHistoryPagination, MovieListView

### Community 136 - "eslint.config.js"
Cohesion: 0.15
Nodes (12): eslint@^9.39.1, @eslint/js@^9.39.1, eslint-plugin-react-hooks@^7.0.1, eslint-plugin-react-refresh@^0.4.24, globals@^16.5.0, typescript-eslint@^8.46.4, eslint, @eslint/js (+4 more)

### Community 137 - "interface"
Cohesion: 0.33
Nodes (5): interface, display_name, short_description, policy, allow_implicit_invocation

### Community 138 - "PasswordResetSecurityTests"
Cohesion: 0.07
Nodes (3): EmailOrUsernameModelBackend, AuthenticationLoggingSecurityTests, PasswordResetSecurityTests

### Community 139 - "Examples"
Cohesion: 0.40
Nodes (4): Example 1: Test failure with stack trace, Example 2: Intermittent test failure, Example 3: Regression after a commit, Examples

### Community 140 - "SwipeSerializer"
Cohesion: 0.33
Nodes (3): SwipeSerializer, Meta, _safe_analytics_callback()

### Community 144 - "dependencies"
Cohesion: 0.17
Nodes (12): dependencies, canvas-confetti@^1.9.4, framer-motion@^12.31.0, lucide-react@^0.577.0, material-symbols@^0.40.2, react@^19.2.0, react-dom@^19.2.0, react-router-dom@^7.12.0 (+4 more)

### Community 147 - "devDependencies"
Cohesion: 0.14
Nodes (13): devDependencies, jsdom@^30.1.3, tailwindcss@^4.1.18, @testing-library/jest-dom@^7.0.1, @testing-library/react@^16.3.3, @types/react@^19.2.5, @types/react-dom@^19.2.3, vitest@^5.1.0 (+5 more)

### Community 150 - "AuthRateThrottle"
Cohesion: 0.18
Nodes (5): AuthRateThrottle, GuestProvisionThrottle, GuestRecoverThrottle, PasswordResetRateThrottle, LoginView

### Community 167 - "4xx — Client-Side Errors"
Cohesion: 0.17
Nodes (12): 4xx — Client-Side Errors, HTTP 400 Bad Request, HTTP 401 Unauthorized, HTTP 403 Forbidden, HTTP 404 Not Found, HTTP 405 Method Not Allowed, HTTP 408 Request Timeout, HTTP 409 Conflict (+4 more)

### Community 171 - "flick-frontend/package.json"
Cohesion: 0.18
Nodes (10): @types/canvas-confetti@^1.9.0, @types/node@^24.10.1, typescript@~5.9.3, name, private, type, version, @types/canvas-confetti (+2 more)

### Community 178 - "Flick — HTTP Status Codes, Server Logs & Error-Handling Reference"
Cohesion: 0.20
Nodes (9): 10. Glossary of Key Technical Terms, 1. Quick-Reference Cheat Sheet, 2. What Are HTTP Status Codes?, 8. Frontend & Build-Related Numbers, At a Glance: What Do These Numbers Mean?, Flick — HTTP Status Codes, Server Logs & Error-Handling Reference, Port Numbers, Table of Contents (+1 more)

### Community 179 - "CorrectSyntheticM1RecordsTest"
Cohesion: 0.07
Nodes (9): Command, _inspect_target_records(), _resolve_staff_user(), _build_candidate_queryset(), Command, _validate_candidate(), CorrectSyntheticM1RecordsTest, _guard_pass() (+1 more)

### Community 180 - "verify-batch-b-browser.js"
Cohesion: 0.21
Nodes (5): puppeteer-core@^25.16.0, SCREENSHOT_DIR, SCREENSHOT_DIR, SCREENSHOT_DIR, puppeteer-core

### Community 184 - "2xx — Successful Responses"
Cohesion: 0.40
Nodes (5): 2xx — Successful Responses, HTTP 200 OK, HTTP 201 Created, HTTP 202 Accepted, HTTP 204 No Content

### Community 186 - "vite.config.ts"
Cohesion: 0.22
Nodes (6): @tailwindcss/vite@^4.1.18, vite@^7.2.4, @vitejs/plugin-react@^5.1.1, @tailwindcss/vite, vite, @vitejs/plugin-react

### Community 191 - "tmdb_changes.py"
Cohesion: 0.17
Nodes (5): Command, PollerLockedError, RateLimitBackoffError, StalePollerOwnershipError, TmdbConfigError

### Community 192 - "WatchlistItem"
Cohesion: 0.12
Nodes (5): WatchlistItem, Meta, DiscoverView, WatchlistDetailView, WatchlistView

### Community 197 - "5. Deep Dive: HTTP 304 Not Modified & Caching"
Cohesion: 0.40
Nodes (5): 5. Deep Dive: HTTP 304 Not Modified & Caching, Conditional Requests (ETag & Last-Modified), How Browser Caching Works, How Caching Is Implemented in Flick, When 304 Is Healthy vs When It Is a Problem

### Community 198 - "GuestProvisioningAPITests"
Cohesion: 0.09
Nodes (3): ExistingRegisteredUserCompatibilityTests, GuestProvisioningAPITests, GuestThrottlingTests

### Community 201 - ".link_guest_to_user"
Cohesion: 0.05
Nodes (10): Command, HistoricalReconciliationService, map_swipe_reaction(), reconcile_historical_interactions(), HistoricalReconciliationServiceTests, InteractionLogProcessingStatusTests, SwipeUndoViewInverseParityTests, Task 3: Historical Interaction Reconciliation Service & Command (+2 more)

### Community 204 - "4. Deciphering Server Logs & Trailing Numbers"
Cohesion: 0.29
Nodes (7): 4. Deciphering Server Logs & Trailing Numbers, Anatomy of a Django/Daphne Access Log, What Do the Trailing Numbers Mean? (The 55 vs 1989 Mystery), Why does `/api/curators-selection/` show `200 1989`?, Why does `/api/users/profile/` show `200 55`?, Why does `GET /api/movies/` show `304 -` or `304 0`?, WSGI vs ASGI Logging Differences

### Community 205 - "TestIndianLanguageDiscovery"
Cohesion: 0.08
Nodes (4): DiscoveryQuerySpec, IndianCatalogueCoverageReport, IndianCatalogueDiscoveryService, TestIndianLanguageDiscovery

### Community 211 - "InMemoryTokenBucket"
Cohesion: 0.15
Nodes (5): InMemoryTokenBucket, 1. The Movie Database (TMDB), 2. Redis, 3. PostgreSQL & SQLite, External Service Failure Modes (TMDB, Redis, Postgres)

### Community 219 - "SecretRedactionFilter"
Cohesion: 0.10
Nodes (4): CorrelationIdFilter, SecretRedactionFilter, SecretRedactionFormatter, SecretRedactionLoggerTests

### Community 244 - "run_staleness_sweep"
Cohesion: 0.08
Nodes (5): StalenessSweepCheckpoint, Meta, run_staleness_sweep(), StalenessSweepService, StalenessSweepTests

## Knowledge Gaps
- **90 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Movie` connect `test_seed_local_dev_catalogue.py` to `HardConstraintFilter`, `Swipe`, `Phase6BatchBBackendTests`, `ShortageRedistributionAndFloorTests`, `_make_movie`, `MovieListView`, `PaginationAndResourceLimitTests`, `handle_catalogue_classification`, `Batch3WorkerIntegrationTests`, `.classify_pool`, `MovieSerializer`, `Batch5PersonalizationEvaluationTests`, `DeckStateAPITests`, `DynamicMovieCatalogueTests`, `WatchlistTests`, `Command`, `Stage3EndToEndProductValidationTests`, `ProposalExecutionWorker`, `Pre1990ReleasePeriodFilterTests`, `SessionLifecycleAndQuestionnaireRecoveryTests`, `SessionQueryOptimizationTests`, `CatalogueJob`, `MatchListFilteringSecurityTests`, `RecommendationDiscoveryTests`, `evaluate_eligibility_predicates`, `test_recommendation_evaluation.py`, `SwipeUndoView`, `admin.py`, `ScreeningSessionResultsAndStatsPersistenceTests`, `views.py`, `_ingest_tmdb_results`, `CorrectSyntheticM1RecordsTest`, `TestCase`, `tmdb.py`, `StreamingProvider`, `tmdb_changes.py`, `WatchlistItem`, `test_proposals.py`, `retrieval.py`, `Phase6BatchCRecentSessionsAndStreamingTests`, `Swipe`, `.link_guest_to_user`, `TestIndianLanguageDiscovery`, `batch_sync_prelaunch.py`, `ArchiveShelvesService`, `IntelligenceModelsTestCase`, `TmdbChangesServiceTests`, `.anonymize_and_delete_user`, `HardConstraints`, `ClassicVaultEraFilterTests`, `PostgreSQLQueueConcurrencyTests`, `PreferenceAndManifestCorrectnessTests`, `TestReliabilityAndRetrieval`, `AuthenticationAndPermissionTests`, `TmdbChangesService`, `StreamingFilterAuditTests`, `BoutiqueManifestCompilationTests`, `SuperLikePersistenceAndAttributionTests`, `Session`, `SuperLikeReactionMatrixIntegrationTests`, `DatabaseConcurrencyAndSwipeReliabilityTests`, `run_staleness_sweep`, `UserPreferenceData`, `TmdbChangesCheckpoint`, `MotionAndSessionRegressionAuditTests`, `SessionHistoryTests`, `StreamingOptionsRemediationTests`, `FunctionalAndMobileAuditVerificationTests`, `CandidateRetrievalAndEligibilityTests`, `CoreUserExperienceRepairTests`?**
  _High betweenness centrality (0.258) - this node is a cross-community bridge._
- **Are the 130 inferred relationships involving `Movie` (e.g. with `Command` and `Command`) actually correct?**
  _`Movie` has 130 INFERRED edges - model-reasoned connections that need verification._
- **Should `HardConstraintFilter` be split into smaller, more focused modules?**
  _Cohesion score 0.13405797101449277 - nodes in this community are weakly interconnected._
- **Why does `6. Flick-Specific Error Handling Architecture` connect `6. Flick-Specific Error Handling Architecture` to `apiRequest`, `Flick — HTTP Status Codes, Server Logs & Error-Handling Reference`, `InMemoryTokenBucket`?**
  _High betweenness centrality (0.155) - this node is a cross-community bridge._
- **Are the 79 inferred relationships involving `Session` (e.g. with `MatchConsumer` and `SessionDetailSerializer`) actually correct?**
  _`Session` has 79 INFERRED edges - model-reasoned connections that need verification._
- **Should `Defense-in-Depth Debugging Strategies` be split into smaller, more focused modules?**
  _Cohesion score 0.06451612903225806 - nodes in this community are weakly interconnected._
- **Why does `Frontend Error Handling (`api.ts` & React)` connect `apiRequest` to `6. Flick-Specific Error Handling Architecture`?**
  _High betweenness centrality (0.154) - this node is a cross-community bridge._