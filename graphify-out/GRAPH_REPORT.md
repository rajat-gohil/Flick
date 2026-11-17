# Graph Report - flick-app  (2026-11-17)

## Corpus Check
- 249 files · ~375,974 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 59 file(s) not represented in the graph (top: .csv 48, (none) 7, .example 2)

## Summary
- 4260 nodes · 9226 edges · 185 communities (94 shown, 91 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 1049 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a6ceceb4`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- UserTasteProfile
- Defense-in-Depth Debugging Strategies
- compute_recovery_lookup_digest
- django_db
- test_seed_local_dev_catalogue.py
- router.tsx
- GuestConversionValidationAndRejectionTests
- WebSocketAuthenticationAndAuthorizationTests
- DiscoverPage.tsx
- apiRequest
- PreferenceAndManifestCorrectnessTests
- tmdb_changes.py
- LocalizedGenreRetrievalTests
- CinemaHeader
- CatalogueJob
- Batch5PersonalizationEvaluationTests
- DynamicMovieCatalogueTests
- CorrelationIdMiddleware
- SessionPage.tsx
- compilerOptions
- ConstraintExhaustionNoticeModal.tsx
- Stage3EndToEndProductValidationTests
- WebSocketRevocationTests
- ProposalExecutionWorker
- ClassicVaultEraFilterTests
- SessionLifecycleAndQuestionnaireRecoveryTests
- permissions.py
- transition_movie_classification
- canonicalize_recovery_code
- Root Cause Tracing Techniques
- compilerOptions
- GuestSecurityHMACAndVerificationTests
- MatchConsumer
- Systematic Debugging
- manifest.json
- ProposalAPITestCase
- GuestProfile
- RecommendationDiscoveryTests
- evaluate_eligibility_predicates
- HardConstraintFilter
- backend/package.json
- models.py
- RecommendationView
- ThemeContext.tsx
- admin.py
- ScreeningSessionResultsAndStatsPersistenceTests
- DesignSystemGenerator
- core/urls.py
- .link_guest_to_user
- Movie
- .agent/skills/ui-ux-pro-max/scripts/design_system.py
- TestCase
- DesignSystemGenerator
- reset_correlation_id
- scripts
- 6. Flick-Specific Error Handling Architecture
- 2xx — Successful Responses
- React + TypeScript + Vite
- vercel.json
- tmdb.py
- .enqueue
- evaluate_eligibility_predicates
- tmdb_rate_limiter.py
- sw.js
- StreamingOptionsRemediationTests
- test_proposals.py
- tsconfig.json
- Session
- GuestActivityTrackingTests
- Phase6BatchCRecentSessionsAndStreamingTests
- ConstraintExpansionProposalSerializer
- test_batch5_personalization.py
- .agent/skills/ui-ux-pro-max/scripts/core.py
- AuthRateThrottle
- .record_swipe_response
- 9. Practical Troubleshooting Playbook
- batch_sync_prelaunch.py
- ArchiveShelvesService
- get_or_create_movie_from_tmdb
- TestIndianLanguageDiscovery
- ui-ux-pro-max
- .anonymize_and_delete_user
- api.ts
- UserIdentityLinkModelTests
- HardConstraints
- GuestProvisioningAPITests
- PasswordResetSecurityTests
- PostgreSQLQueueConcurrencyTests
- ui-ux-pro-max
- .agents/skills/ui-ux-pro-max/scripts/design_system.py
- MovieQuerySetRestrictionTests
- UserIdentityLink
- set_redis_client
- RecoveryHandoffReliabilityTests
- AuthenticationAndPermissionTests
- .agent/skills/ui-ux-pro-max/scripts/search.py
- AuthenticationThrottlingTests
- Pre1990ReleasePeriodFilterTests
- StreamingFilterAuditTests
- .generate_targeted_discovery_plan
- UniversalLocalNetworkDevConfigurationTests
- 7. Background Queue & Worker Numbers
- BoutiqueManifestCompilationTests
- dependencies
- tmdb.py
- SessionDetailSerializer
- GuestProfileModelTests
- StreamingProvider
- AdminCommandSecurityTests
- SessionPage.tsx
- Workflow Phases (Summary)
- SessionJoiningTests
- .score
- GuestRecoveryConcurrencyTests
- SettingsSecurityTests
- 5xx — Server-Side & Upstream Errors
- SwipeUndoTests
- SessionEndView
- calculate_entropy_bits
- diagnose_lan_connectivity.sh
- CandidateRetrievalAndEligibilityTests
- IndianCatalogueCoverageReport
- Phase6BatchBBackendTests
- SwipeAndMatchingTests
- middleware.py
- CoreUserExperienceRepairTests
- SessionCodeCollisionTests
- ConcurrencyAndAtomicityTests
- SessionResetPreferencesView
- PaginationAndResourceLimitTests
- eslint.config.js
- interface
- PasswordResetSecurityTests
- Examples
- Session
- test_guest_api.py
- EmailVerificationTests
- PreferencesPage.tsx
- devDependencies
- GuestActivityMiddleware
- DiscoverTests
- MovieSerializer
- SwipeFailureRecoveryAndEdgeCaseTests
- MatchListFilteringSecurityTests
- AffinityEvaluationTests
- GuestConversionConcurrencyTests
- get_correlation_id
- WatchlistTests
- Command
- calculate_preference_score
- 4xx — Client-Side Errors
- SessionQueryOptimizationTests
- flick-frontend/package.json
- views.py
- vercel.json
- Flick — HTTP Status Codes, Server Logs & Error-Handling Reference
- CorrectSyntheticM1RecordsTest
- verify-batch-b-browser.js
- HealthCheckView
- vite.config.ts
- parse_retry_after
- 5. Deep Dive: HTTP 304 Not Modified & Caching
- GuestRecoveryAPITests
- HistoricalReconciliationService
- 4. Deciphering Server Logs & Trailing Numbers
- IntelligenceModelsTestCase
- InMemoryTokenBucket
- SecretRedactionFilter
- SuperLikeReactionMatrixIntegrationTests
- DatabaseConcurrencyAndSwipeReliabilityTests
- MotionAndSessionRegressionAuditTests
- SessionHistoryTests
- Command
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
- `2. Secret Redaction Filter (`core/logging.py`)` --references--> `SecretRedactionFilter`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/logging.py
- `Anatomy of a Django/Daphne Access Log` --references--> `CorrelationIdMiddleware`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/middleware.py
- `Worker Leases, Fencing Tokens & Heartbeats` --references--> `StaleLeaseOwnershipError`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/services/catalogue_queue.py
- `Task 4: Guest Identity Linking Service` --references--> `IdentityLinkingService`  [INFERRED]
  tasks/plan.md → backend/core/services/identity_linking.py
- `HTTP 403 Forbidden` --references--> `transition_movie_classification()`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/services/movie_mutations.py

## Import Cycles
- None detected.

## Communities (185 total, 91 thin omitted)

### Community 0 - "UserTasteProfile"
Cohesion: 0.07
Nodes (8): MovieExposure, UserTasteProfile, DuplicateIdentityLinkError, _movie_contains(), _movie_get(), _movie_getitem(), PersonalizedRecommendationEngine, _pluralize_genre()

### Community 1 - "Defense-in-Depth Debugging Strategies"
Cohesion: 0.06
Nodes (30): Boundary Testing, Checkpoint: Layered debugging complete, Cleanup and teardown, Defense-in-Depth Debugging Strategies, Dependency isolation, Divide and Conquer, Hypothesis Testing Protocol, Input validation (+22 more)

### Community 2 - "compute_recovery_lookup_digest"
Cohesion: 0.14
Nodes (5): compute_recovery_lookup_digest(), dummy_verify_recovery_code(), generate_recovery_code(), hash_recovery_code(), verify_recovery_code()

### Community 3 - "django_db"
Cohesion: 0.03
Nodes (39): Migration, Migration, Migration, Migration, Migration, Migration, Migration, Migration (+31 more)

### Community 4 - "test_seed_local_dev_catalogue.py"
Cohesion: 0.04
Nodes (17): _assert_safe_local_database(), _build_candidate_queryset(), Command, _resolve_canonical_db_path(), _validate_candidate(), fetch_tmdb_movies(), CandidatePrevalidationTest, DryRunImmutabilityTest (+9 more)

### Community 5 - "router.tsx"
Cohesion: 0.13
Nodes (25): AccountSettingsPage, AnimatedRoutes(), AutoJoin, CreateSessionPage, DiscoverPage, EntryPage, ForgotPasswordPage, GuestConvertPage (+17 more)

### Community 8 - "DiscoverPage.tsx"
Cohesion: 0.06
Nodes (31): Provider, ProviderLogo(), streamingCache, StreamingData, StreamingOptions(), ArchiveShelf, ArchiveShelfSection(), CatalogueSort (+23 more)

### Community 9 - "apiRequest"
Cohesion: 0.10
Nodes (31): 1. The `ApiError` Class, 3. Automatic Session Expiration Handling (401 Interceptor), 4. Empty States vs. Actual Errors, Frontend Error Handling (`api.ts` & React), AuthShell(), generateUsernameSuggestions(), getPasswordStrength(), STEPS (+23 more)

### Community 11 - "tmdb_changes.py"
Cohesion: 0.05
Nodes (11): Command, TmdbChangesCheckpoint, Meta, poll_tmdb_changes(), PollerLockedError, RateLimitBackoffError, StalePollerOwnershipError, TmdbChangesService (+3 more)

### Community 12 - "LocalizedGenreRetrievalTests"
Cohesion: 0.09
Nodes (3): LocalizedGenreRetrievalTests, fake_ingest(), fake_ingest()

### Community 13 - "CinemaHeader"
Cohesion: 0.08
Nodes (40): posthog-js@^1.319.0, BottomNav(), BottomNavProps, NavTab, CinemaHeader(), CinemaHeaderProps, trackEvent(), CreateSessionPage() (+32 more)

### Community 14 - "CatalogueJob"
Cohesion: 0.04
Nodes (17): register_handler(), reset_handlers(), CatalogueJob, JobType, Meta, Status, StalenessSweepCheckpoint, Meta (+9 more)

### Community 16 - "DynamicMovieCatalogueTests"
Cohesion: 0.05
Nodes (3): DynamicMovieCatalogueTests, FunctionalAndMobileAuditVerificationTests, StreamingProviderAvailabilityTests

### Community 18 - "SessionPage.tsx"
Cohesion: 0.07
Nodes (42): DeckCardSkeleton(), MatchItemSkeleton(), MovieCardSkeleton(), ShelfSkeleton(), Skeleton(), SkeletonProps, StreamingItemSkeleton(), getWsBaseUrl() (+34 more)

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
Cohesion: 0.07
Nodes (4): Command, ProposalExecutionWorker, ProposalLifecycleAndIdempotencyTestCase, ProposalOutboxWorkerTestCase

### Community 26 - "permissions.py"
Cohesion: 0.15
Nodes (4): configure_sqlite_pragmas(), CoreConfig, CoreConfig, IsOwner

### Community 29 - "Root Cause Tracing Techniques"
Cohesion: 0.07
Nodes (26): Checkpoint: When investigation is complete, Common Root Cause Patterns, Component Boundary Tracing, Configuration mismatch, Data Flow Analysis, Diff-based investigation, Error Message Anatomy, Example: Wrong calculation (+18 more)

### Community 30 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 31 - "GuestSecurityHMACAndVerificationTests"
Cohesion: 0.12
Nodes (3): get_recovery_hmac_key(), GuestSecurityDeploymentSettingsTests, GuestSecurityHMACAndVerificationTests

### Community 33 - "Systematic Debugging"
Cohesion: 0.12
Nodes (15): Do not use this skill when, Examples, First move, Guardrails, Inputs to gather, Outputs, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis (+7 more)

### Community 34 - "manifest.json"
Cohesion: 0.12
Nodes (16): background_color, categories, description, display, icons, lang, name, orientation (+8 more)

### Community 36 - "GuestProfile"
Cohesion: 0.10
Nodes (4): GuestProfile, Meta, GuestConversionRecoverySecurityTests, GuestConversionSuccessTests

### Community 38 - "evaluate_eligibility_predicates"
Cohesion: 0.15
Nodes (3): validate_movie_language(), LanguageValidationTests, MovieEligibilityModelAndSignalTests

### Community 40 - "backend/package.json"
Cohesion: 0.36
Nodes (7): devDependencies, autoprefixer@^10.4.23, postcss@^8.5.6, tailwindcss@^4.1.18, tailwindcss, autoprefixer, postcss

### Community 41 - "models.py"
Cohesion: 0.08
Nodes (9): Command, Command, Genre, MovieManager, Swipe, Meta, UserProfile, GuestConversionDataIntegrityTests (+1 more)

### Community 42 - "RecommendationView"
Cohesion: 0.14
Nodes (8): SessionChemistry, Meta, UserTasteSignal, Meta, normalize_pair(), RecommendationView, SwipeUndoView, _update_analytics_after_commit()

### Community 43 - "ThemeContext.tsx"
Cohesion: 0.15
Nodes (14): App(), AppRouter(), RouteLoadingFallback(), CinematicLoader(), CinematicLoaderProps, FLICK_LOGOS, Theme, ThemeContext (+6 more)

### Community 44 - "admin.py"
Cohesion: 0.20
Nodes (11): CustomUserAdmin, GenreAdmin, MatchAdmin, MovieAdmin, MovieStreamingAvailabilityAdmin, SessionAdmin, SessionStatsAdmin, StreamingProviderAdmin (+3 more)

### Community 47 - "core/urls.py"
Cohesion: 0.05
Nodes (24): DeckSwipeUndoView, DeleteAccountView, GenreSyncTMDBView, GuestConvertView, GuestProvisionView, GuestRecoverView, GuestRecoveryAckView, GuestRotateCodeView (+16 more)

### Community 48 - ".link_guest_to_user"
Cohesion: 0.11
Nodes (9): IdentityLinkingService, IdentityLinkingServiceTests, Batch 4: Historical Interaction Reconciliation & Identity Linking — Task List, Checkpoint 1: Foundations Complete, Checkpoint 2: Reconciliation & Identity Complete, Checkpoint 3: Batch 4 Complete, Phase 1: Foundations & Parity, Phase 2: Reconciliation & Identity (+1 more)

### Community 49 - "Movie"
Cohesion: 0.04
Nodes (22): Command, Command, Command, Movie, movie_genres_changed_handler(), recalculate_movie_eligibility(), register_eligibility_signals(), acquire_tmdb_token() (+14 more)

### Community 50 - ".agent/skills/ui-ux-pro-max/scripts/design_system.py"
Cohesion: 0.14
Nodes (8): _detect_page_type(), format_ascii_box(), format_markdown(), format_master_md(), format_page_override_md(), generate_design_system(), _generate_intelligent_overrides(), persist_design_system()

### Community 51 - "TestCase"
Cohesion: 0.10
Nodes (4): GenreIntegrationTests, LocalNetworkConfigurationTests, RecentSessionsTests, SessionLifecycleTests

### Community 53 - "reset_correlation_id"
Cohesion: 0.17
Nodes (3): reset_correlation_id(), set_correlation_id(), TMDBOutboundHeaderPropagationTests

### Community 54 - "scripts"
Cohesion: 0.33
Nodes (6): scripts, build, dev, lint, preview, test

### Community 55 - "6. Flick-Specific Error Handling Architecture"
Cohesion: 0.22
Nodes (9): 1. Custom Exception Handler (`backend/backend/exceptions.py`), 1. The Movie Database (TMDB), 2. Redis, 2. Secret Redaction Filter (`core/logging.py`), 3. PostgreSQL & SQLite, 3. Request Correlation ID Middleware (`core/middleware.py`), 6. Flick-Specific Error Handling Architecture, Backend Error Handling (DRF, Exceptions & Middleware) (+1 more)

### Community 56 - "2xx — Successful Responses"
Cohesion: 0.20
Nodes (10): 2xx — Successful Responses, 3. Complete HTTP Status Code Guide, 3xx — Redirection & Caching, HTTP 200 OK, HTTP 201 Created, HTTP 202 Accepted, HTTP 204 No Content, HTTP 301 Moved Permanently (+2 more)

### Community 57 - "React + TypeScript + Vite"
Cohesion: 0.50
Nodes (3): Expanding the ESLint configuration, React Compiler, React + TypeScript + Vite

### Community 59 - "tmdb.py"
Cohesion: 0.07
Nodes (28): Migration, discover_movies(), _fetch(), fetch_cached_tmdb(), format_tmdb_movie(), get_genres_map(), _fetch(), get_movie_watch_providers() (+20 more)

### Community 60 - ".enqueue"
Cohesion: 0.03
Nodes (6): IntelligenceWorkerProcess, _beat(), CatalogueQueueService, Batch2EnrichmentAndWorkerTests, Batch3WorkerIntegrationTests, CatalogueQueueUnitTests

### Community 62 - "tmdb_rate_limiter.py"
Cohesion: 0.06
Nodes (12): acquire_tmdb_token(), calculate_cooldown_with_jitter(), get_rate_limiter_status(), get_redis_client(), is_production(), record_tmdb_429(), _redis_eval_acquire(), _redis_eval_record_429() (+4 more)

### Community 65 - "test_proposals.py"
Cohesion: 0.07
Nodes (13): ConstraintExpansionProposal, Meta, ProposalOutboxMessage, Meta, ProposalError, ProposalExpiredError, ProposalInvalidStateError, ProposalNotFoundError (+5 more)

### Community 67 - "Session"
Cohesion: 0.06
Nodes (29): CollaborativeAgreement, Match, Meta, SessionOccasionState, SessionStats, calculate_questionnaire_similarity(), calculate_screening_affinity(), calculate_session_statistics() (+21 more)

### Community 70 - "ConstraintExpansionProposalSerializer"
Cohesion: 0.21
Nodes (4): ConstraintExpansionProposalSerializer, Meta, ProposalDetailView, ProposalListCreateView

### Community 71 - "test_batch5_personalization.py"
Cohesion: 0.07
Nodes (10): compute_cohort_divergence(), compute_negative_response_rate(), compute_preference_alignment(), compute_shelf_diversity(), compute_unexposed_discovery_ratio(), _extract_movie_id(), _extract_movie_tokens(), RecommendationEvaluationService (+2 more)

### Community 72 - ".agent/skills/ui-ux-pro-max/scripts/core.py"
Cohesion: 0.06
Nodes (12): BM25, detect_domain(), _load_csv(), search(), _search_csv(), search_stack(), BM25, detect_domain() (+4 more)

### Community 73 - "AuthRateThrottle"
Cohesion: 0.09
Nodes (8): AuthRateThrottle, GuestProvisionThrottle, GuestRecoverThrottle, PasswordResetRateThrottle, LoginView, PasswordResetRequestView, RegisterView, SendVerificationEmailView

### Community 74 - ".record_swipe_response"
Cohesion: 0.03
Nodes (12): DeckStateError, InvalidCardIndexError, OutOfOrderResponseError, StaleManifestError, DeckStateConcurrencyTests, submit_duplicate(), submit_guest(), submit_host() (+4 more)

### Community 79 - "9. Practical Troubleshooting Playbook"
Cohesion: 0.12
Nodes (17): 10. `502 Bad Gateway`, 11. `503 Service Unavailable`, 12. `504 Gateway Timeout`, 13. `ConnectionResetError(54, 'Connection reset by peer')`, 14. `ECONNREFUSED 127.0.0.1:8000`, 15. `AbortError: The operation was aborted`, 16. `CatalogueJob status = failed_permanent`, 1. `200 55` (+9 more)

### Community 80 - "batch_sync_prelaunch.py"
Cohesion: 0.21
Nodes (3): Command, _make_session(), _tmdb_get()

### Community 81 - "ArchiveShelvesService"
Cohesion: 0.14
Nodes (3): ArchiveShelvesService, CuratorsSelectionView, YourArchiveView

### Community 82 - "get_or_create_movie_from_tmdb"
Cohesion: 0.17
Nodes (5): get_enhanced_movie_details(), get_movie_by_tmdb_id(), get_movie_genres(), get_movie_trailer_key(), get_or_create_movie_from_tmdb()

### Community 84 - "ui-ux-pro-max"
Cohesion: 0.07
Nodes (29): Accessibility, Available Domains, Available Stacks, Common Rules for Professional UI, Example Workflow, How to Use This Skill, Icons & Visual Elements, Interaction (+21 more)

### Community 85 - ".anonymize_and_delete_user"
Cohesion: 0.12
Nodes (4): TombstoneService, TombstoneServiceTests, DeleteAccountEndpointTests, Task 6: Privacy-Preserving Tombstone Anonymization

### Community 86 - "api.ts"
Cohesion: 0.11
Nodes (29): RecoveryCodeModal(), RecoveryCodeModalProps, acknowledgeRecovery(), buildDeduplicationKey(), clearInFlightRequests(), convertGuestAccount(), getBaseUrl, getInFlightRequestCount() (+21 more)

### Community 88 - "HardConstraints"
Cohesion: 0.04
Nodes (8): CollaborativeDeckScorer, ScoredCandidate, CandidatePool, HardConstraints, UserPreferenceData, ManifestLearnedFeedbackIntegrationTests, ReproducibilityAndPersistenceTests, RoomRecommendationScenariosTestCase

### Community 91 - "PostgreSQLQueueConcurrencyTests"
Cohesion: 0.12
Nodes (3): PostgreSQLQueueConcurrencyTests, do_enqueue(), worker_task()

### Community 92 - "ui-ux-pro-max"
Cohesion: 0.07
Nodes (29): Accessibility, Available Domains, Available Stacks, Common Rules for Professional UI, Example Workflow, How to Use This Skill, Icons & Visual Elements, Interaction (+21 more)

### Community 93 - ".agents/skills/ui-ux-pro-max/scripts/design_system.py"
Cohesion: 0.14
Nodes (8): _detect_page_type(), format_ascii_box(), format_markdown(), format_master_md(), format_page_override_md(), generate_design_system(), _generate_intelligent_overrides(), persist_design_system()

### Community 95 - "UserIdentityLink"
Cohesion: 0.05
Nodes (11): MovieKeyword, MovieTag, UserIdentityLink, LinkType, Meta, handle_recompute_taste_profile(), recompute_user_taste_profile(), TasteEngineService (+3 more)

### Community 96 - "set_redis_client"
Cohesion: 0.12
Nodes (3): reset_rate_limiter(), set_redis_client(), TMDBRateLimiterRedisLuaMockTests

### Community 99 - ".agent/skills/ui-ux-pro-max/scripts/search.py"
Cohesion: 0.11
Nodes (4): format_output(), format_output(), main(), start.sh script

### Community 106 - "7. Background Queue & Worker Numbers"
Cohesion: 0.40
Nodes (5): 7. Background Queue & Worker Numbers, Queue Priorities & Fair Scheduling Quotas, Retry Limits, Exponential Backoff & Quarantine, TMDB Dual-Bucket Rate Limiter Constants, Worker Leases, Fencing Tokens & Heartbeats

### Community 107 - "BoutiqueManifestCompilationTests"
Cohesion: 0.07
Nodes (4): BoutiqueManifestCompilationTests, HamiltonManifestAllocatorTests, NormalManifestCompilationTests, ShortageRedistributionAndFloorTests

### Community 108 - "dependencies"
Cohesion: 0.17
Nodes (12): dependencies, canvas-confetti@^1.9.4, framer-motion@^12.31.0, lucide-react@^0.577.0, material-symbols@^0.40.2, react@^19.2.0, react-dom@^19.2.0, react-router-dom@^7.12.0 (+4 more)

### Community 109 - "tmdb.py"
Cohesion: 0.13
Nodes (5): _create_tmdb_session(), get_tmdb_session(), reset_tmdb_session(), Phase6BatchCTMDBReliabilityTests, worker()

### Community 112 - "StreamingProvider"
Cohesion: 0.17
Nodes (7): Command, Command, MovieStreamingAvailability, Meta, StreamingProvider, _link_streaming_availability(), resolve_streaming_provider_ids()

### Community 114 - "SessionPage.tsx"
Cohesion: 0.05
Nodes (39): 2. Automatic Error Message Extraction, ErrorBoundary, Props, State, ApiError, MenuItem(), ProfilePage(), ThemeToggleItem() (+31 more)

### Community 115 - "Workflow Phases (Summary)"
Cohesion: 0.25
Nodes (7): Common Rationalisations, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis, Phase 3: Hypothesis and Testing, Phase 4: Implementation, Phases, Red Flags, and Common Rationalisations, Workflow Phases (Summary)

### Community 120 - "5xx — Server-Side & Upstream Errors"
Cohesion: 0.40
Nodes (5): 5xx — Server-Side & Upstream Errors, HTTP 500 Internal Server Error, HTTP 502 Bad Gateway, HTTP 503 Service Unavailable, HTTP 504 Gateway Timeout

### Community 122 - "SessionEndView"
Cohesion: 0.20
Nodes (4): compute_session_statistics(), MatchListView, serialize_session_matches(), SessionEndView

### Community 130 - "middleware.py"
Cohesion: 0.12
Nodes (3): get_user_from_token_key(), TokenAuthMiddleware, TokenAuthMiddlewareStack()

### Community 136 - "eslint.config.js"
Cohesion: 0.15
Nodes (12): eslint@^9.39.1, @eslint/js@^9.39.1, eslint-plugin-react-hooks@^7.0.1, eslint-plugin-react-refresh@^0.4.24, globals@^16.5.0, typescript-eslint@^8.46.4, eslint, @eslint/js (+4 more)

### Community 137 - "interface"
Cohesion: 0.33
Nodes (5): interface, display_name, short_description, policy, allow_implicit_invocation

### Community 139 - "Examples"
Cohesion: 0.40
Nodes (4): Example 1: Test failure with stack trace, Example 2: Intermittent test failure, Example 3: Regression after a commit, Examples

### Community 140 - "Session"
Cohesion: 0.08
Nodes (15): Session, GenreSerializer, Meta, ProposalOutboxMessageSerializer, Meta, RegisterSerializer, Meta, SessionSerializer (+7 more)

### Community 144 - "PreferencesPage.tsx"
Cohesion: 0.14
Nodes (14): OptionIcon(), PreferencesPage(), buildPreferences(), checkSessionState(), handleNext(), handleSubmit(), loadAuthoritativeState(), Question (+6 more)

### Community 147 - "devDependencies"
Cohesion: 0.14
Nodes (13): devDependencies, jsdom@^30.1.3, tailwindcss@^4.1.18, @testing-library/jest-dom@^7.0.1, @testing-library/react@^16.3.3, @types/react@^19.2.5, @types/react-dom@^19.2.3, vitest@^5.1.0 (+5 more)

### Community 153 - "MovieSerializer"
Cohesion: 0.07
Nodes (11): WatchlistItem, Meta, MovieSerializer, Meta, DiscoverView, MovieCreateView, MovieDetailView, MovieUpdateView (+3 more)

### Community 162 - "get_correlation_id"
Cohesion: 0.15
Nodes (7): get_correlation_id(), CorrelationIdConcurrencyTests, run_all(), worker(), async_view(), __init__(), failing_view()

### Community 167 - "4xx — Client-Side Errors"
Cohesion: 0.17
Nodes (12): 4xx — Client-Side Errors, HTTP 400 Bad Request, HTTP 401 Unauthorized, HTTP 403 Forbidden, HTTP 404 Not Found, HTTP 405 Method Not Allowed, HTTP 408 Request Timeout, HTTP 409 Conflict (+4 more)

### Community 171 - "flick-frontend/package.json"
Cohesion: 0.18
Nodes (10): @types/canvas-confetti@^1.9.0, @types/node@^24.10.1, typescript@~5.9.3, name, private, type, version, @types/canvas-confetti (+2 more)

### Community 172 - "views.py"
Cohesion: 0.05
Nodes (14): MovieTagRelation, Meta, StandardResultsSetPagination, SwipeHistoryPagination, ReplenishmentInProgressError, TransientReplenishmentError, DeckCardDeliveryView, ensure_default_genres() (+6 more)

### Community 178 - "Flick — HTTP Status Codes, Server Logs & Error-Handling Reference"
Cohesion: 0.20
Nodes (9): 10. Glossary of Key Technical Terms, 1. Quick-Reference Cheat Sheet, 2. What Are HTTP Status Codes?, 8. Frontend & Build-Related Numbers, At a Glance: What Do These Numbers Mean?, Flick — HTTP Status Codes, Server Logs & Error-Handling Reference, Port Numbers, Table of Contents (+1 more)

### Community 179 - "CorrectSyntheticM1RecordsTest"
Cohesion: 0.12
Nodes (5): Command, _inspect_target_records(), _resolve_staff_user(), CorrectSyntheticM1RecordsTest, _guard_pass()

### Community 180 - "verify-batch-b-browser.js"
Cohesion: 0.21
Nodes (5): puppeteer-core@^25.16.0, SCREENSHOT_DIR, SCREENSHOT_DIR, SCREENSHOT_DIR, puppeteer-core

### Community 186 - "vite.config.ts"
Cohesion: 0.22
Nodes (6): @tailwindcss/vite@^4.1.18, vite@^7.2.4, @vitejs/plugin-react@^5.1.1, @tailwindcss/vite, vite, @vitejs/plugin-react

### Community 197 - "5. Deep Dive: HTTP 304 Not Modified & Caching"
Cohesion: 0.40
Nodes (5): 5. Deep Dive: HTTP 304 Not Modified & Caching, Conditional Requests (ETag & Last-Modified), How Browser Caching Works, How Caching Is Implemented in Flick, When 304 Is Healthy vs When It Is a Problem

### Community 201 - "HistoricalReconciliationService"
Cohesion: 0.05
Nodes (21): Command, InteractionLog, Meta, HistoricalReconciliationService, map_swipe_reaction(), reconcile_historical_interactions(), HistoricalReconciliationServiceTests, InteractionLogProcessingStatusTests (+13 more)

### Community 204 - "4. Deciphering Server Logs & Trailing Numbers"
Cohesion: 0.29
Nodes (7): 4. Deciphering Server Logs & Trailing Numbers, Anatomy of a Django/Daphne Access Log, What Do the Trailing Numbers Mean? (The 55 vs 1989 Mystery), Why does `/api/curators-selection/` show `200 1989`?, Why does `/api/users/profile/` show `200 55`?, Why does `GET /api/movies/` show `304 -` or `304 0`?, WSGI vs ASGI Logging Differences

### Community 219 - "SecretRedactionFilter"
Cohesion: 0.10
Nodes (4): CorrelationIdFilter, SecretRedactionFilter, SecretRedactionFormatter, SecretRedactionLoggerTests

## Knowledge Gaps
- **91 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Movie` connect `Movie` to `UserTasteProfile`, `Phase6BatchBBackendTests`, `SwipeAndMatchingTests`, `CoreUserExperienceRepairTests`, `test_seed_local_dev_catalogue.py`, `ConcurrencyAndAtomicityTests`, `PaginationAndResourceLimitTests`, `PreferenceAndManifestCorrectnessTests`, `tmdb_changes.py`, `Session`, `LocalizedGenreRetrievalTests`, `CatalogueJob`, `Batch5PersonalizationEvaluationTests`, `DeckStateAPITests`, `DynamicMovieCatalogueTests`, `Stage3EndToEndProductValidationTests`, `ProposalExecutionWorker`, `ClassicVaultEraFilterTests`, `MovieSerializer`, `SessionLifecycleAndQuestionnaireRecoveryTests`, `transition_movie_classification`, `SwipeFailureRecoveryAndEdgeCaseTests`, `DiscoverTests`, `MatchListFilteringSecurityTests`, `AffinityEvaluationTests`, `WatchlistTests`, `RecommendationDiscoveryTests`, `evaluate_eligibility_predicates`, `HardConstraintFilter`, `models.py`, `SessionQueryOptimizationTests`, `RecommendationView`, `admin.py`, `ScreeningSessionResultsAndStatsPersistenceTests`, `views.py`, `core/urls.py`, `CorrectSyntheticM1RecordsTest`, `tmdb.py`, `.enqueue`, `StreamingOptionsRemediationTests`, `test_proposals.py`, `Session`, `Phase6BatchCRecentSessionsAndStreamingTests`, `test_batch5_personalization.py`, `HistoricalReconciliationService`, `.record_swipe_response`, `batch_sync_prelaunch.py`, `ArchiveShelvesService`, `get_or_create_movie_from_tmdb`, `TestIndianLanguageDiscovery`, `IntelligenceModelsTestCase`, `.anonymize_and_delete_user`, `HardConstraints`, `PostgreSQLQueueConcurrencyTests`, `MovieQuerySetRestrictionTests`, `UserIdentityLink`, `AuthenticationAndPermissionTests`, `Pre1990ReleasePeriodFilterTests`, `StreamingFilterAuditTests`, `BoutiqueManifestCompilationTests`, `SuperLikeReactionMatrixIntegrationTests`, `StreamingProvider`, `DatabaseConcurrencyAndSwipeReliabilityTests`, `.score`, `MotionAndSessionRegressionAuditTests`, `SessionHistoryTests`, `SwipeUndoTests`, `CandidateRetrievalAndEligibilityTests`?**
  _High betweenness centrality (0.244) - this node is a cross-community bridge._
- **Are the 130 inferred relationships involving `Movie` (e.g. with `Command` and `Command`) actually correct?**
  _`Movie` has 130 INFERRED edges - model-reasoned connections that need verification._
- **Should `UserTasteProfile` be split into smaller, more focused modules?**
  _Cohesion score 0.07013574660633484 - nodes in this community are weakly interconnected._
- **Why does `6. Flick-Specific Error Handling Architecture` connect `6. Flick-Specific Error Handling Architecture` to `apiRequest`, `Flick — HTTP Status Codes, Server Logs & Error-Handling Reference`?**
  _High betweenness centrality (0.161) - this node is a cross-community bridge._
- **Are the 79 inferred relationships involving `Session` (e.g. with `MatchConsumer` and `SessionDetailSerializer`) actually correct?**
  _`Session` has 79 INFERRED edges - model-reasoned connections that need verification._
- **Should `Defense-in-Depth Debugging Strategies` be split into smaller, more focused modules?**
  _Cohesion score 0.06451612903225806 - nodes in this community are weakly interconnected._
- **Why does `apiRequest()` connect `apiRequest` to `DiscoverPage.tsx`, `ThemeContext.tsx`, `CinemaHeader`, `PreferencesPage.tsx`, `SessionPage.tsx`, `SessionPage.tsx`, `ConstraintExhaustionNoticeModal.tsx`, `api.ts`?**
  _High betweenness centrality (0.152) - this node is a cross-community bridge._