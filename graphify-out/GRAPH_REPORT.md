# Graph Report - flick-app  (2026-11-23)

## Corpus Check
- 282 files · ~419,218 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 59 file(s) not represented in the graph (top: .csv 48, (none) 7, .example 2)

## Summary
- 4597 nodes · 10280 edges · 189 communities (101 shown, 88 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 1163 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `132edaef`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- StreamingFilterAuditTests
- Defense-in-Depth Debugging Strategies
- guestProvisionCoordinator.ts
- HomePage.tsx
- _make_movie
- apiRequest
- GuestConversionValidationAndRejectionTests
- WebSocketAuthenticationAndAuthorizationTests
- DiscoverPage.tsx
- vitest
- SessionDetailSerializer
- HardConstraints
- tmdb.py
- BottomNav
- run_staleness_sweep
- tutorialSystem.test.tsx
- FunctionalAndMobileAuditVerificationTests
- .get_recommendations
- SessionPage.tsx
- compilerOptions
- ConstraintExhaustionNoticeModal.tsx
- WebSocketRevocationTests
- UserPreferenceData
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
- Stage3EndToEndProductValidationTests
- IntelligenceWorkerProcess
- backend/package.json
- trackEvent
- os
- _get_tmdb_request_headers
- test_seed_local_dev_catalogue.py
- ScreeningSessionResultsAndStatsPersistenceTests
- DesignSystemGenerator
- core/urls.py
- AuthenticationAndPermissionTests
- MatchListFilteringSecurityTests
- .agent/skills/ui-ux-pro-max/scripts/design_system.py
- router.tsx
- DesignSystemGenerator
- merge_guest_activity
- scripts
- UniversalLocalNetworkDevConfigurationTests
- 2xx — Successful Responses
- React + TypeScript + Vite
- vercel.json
- Phase6BatchCRecentSessionsAndStreamingTests
- flick-frontend/package.json
- evaluate_eligibility_predicates
- LocalizedGenreRetrievalTests
- sw.js
- CatalogueQueueService
- CandidateRetrievalAndEligibilityTests
- tsconfig.json
- acquire_tmdb_token
- GuestActivityTrackingTests
- tmdb_rate_limiter.py
- HistoricalReconciliationService
- .recompute_user_taste_profile
- TmdbChangesService
- Batch5PersonalizationEvaluationTests
- devDependencies
- 9. Practical Troubleshooting Playbook
- .agents/skills/ui-ux-pro-max/scripts/core.py
- MovieSerializer
- AdminCommandSecurityTests
- InteractionLog
- ui-ux-pro-max
- UserTasteProfile
- ProposalExecutionWorker
- os
- Session
- SwipeUndoTests
- .authenticate
- PostgreSQLQueueConcurrencyTests
- ui-ux-pro-max
- .agents/skills/ui-ux-pro-max/scripts/design_system.py
- AffinityEvaluationTests
- tests.py
- IdentityLinkingService
- .claim_jobs
- models.py
- GuestSecurityCryptoTests
- AuthenticationThrottlingTests
- production_settings.py
- UserPreferenceData
- ArchiveShelvesService
- GuestProfile
- TestReliabilityAndRetrieval
- admin.py
- test_observability_and_security.py
- CoreUserExperienceRepairTests
- enrichment_handlers.py
- WatchlistBatchAPITests
- InteractionLogProcessingStatusTests
- SoundSynthesizer
- SessionExpandConstraintsView
- DynamicMovieCatalogueTests
- Workflow Phases (Summary)
- throttling.py
- CorrelationIdMiddlewareTests
- TestIngestionAndProvenance
- GuestProvisioningAPITests
- ProposalDecideView
- Pre1990ReleasePeriodFilterTests
- GuestActivityMiddleware
- eslint.config.js
- diagnose_lan_connectivity.sh
- SessionJoiningTests
- TestIndianLanguageDiscovery
- dependencies
- Phase6BatchBBackendTests
- DeckStateAPITests
- SwipeAndMatchingTests
- ProposalLifecycleAndIdempotencyTestCase
- TmdbChangesCheckpoint
- batch_sync_prelaunch.py
- SecretRedactionLoggerTests
- SettingsSecurityTests
- interface
- SwipeFailureRecoveryAndEdgeCaseTests
- Examples
- Movie
- .agent/skills/ui-ux-pro-max/scripts/core.py
- PasswordResetSecurityTests
- Session
- BM25
- MovieQuerySetRestrictionTests
- Command
- .generate_targeted_discovery_plan
- DatabaseConcurrencyAndSwipeReliabilityTests
- HamiltonManifestAllocatorTests
- MotionAndSessionRegressionAuditTests
- calculate_preference_score
- UserIdentityLinkModelTests
- BM25
- parse_retry_after
- Match
- 5. Deep Dive: HTTP 304 Not Modified & Caching
- IntelligenceModelsTestCase
- ProposalExecutionWorker
- GuestConversionConcurrencyTests
- _validate_candidate
- .agent/skills/ui-ux-pro-max/scripts/search.py
- vite.config.ts
- 4xx — Client-Side Errors
- TokenAuthMiddleware
- get_correlation_id
- MovieListView
- get_movie_by_tmdb_id
- SecretRedactionFilter
- Command
- MovieEligibilityModelAndSignalTests
- vercel.json
- SessionChemistry
- Flick — HTTP Status Codes, Server Logs & Error-Handling Reference
- CorrectSyntheticM1RecordsTest
- verify-batch-b-browser.js
- Command
- Command
- get_tmdb_genres
- HardConstraintFilter
- CuratorsSelectionView
- 4. Deciphering Server Logs & Trailing Numbers
- fetch_cached_tmdb
- InMemoryTokenBucket
- TMDBOutboundHeaderPropagationTests

## God Nodes (most connected - your core abstractions)
1. `Movie` - 221 edges
2. `Session` - 140 edges
3. `Genre` - 101 edges
4. `Swipe` - 83 edges
5. `apiRequest()` - 81 edges
6. `UserPreferenceData` - 74 edges
7. `InteractionLog` - 71 edges
8. `HardConstraints` - 70 edges
9. `UserTasteProfile` - 64 edges
10. `CollaborativeAgreement` - 62 edges

## Surprising Connections (you probably didn't know these)
- `Anatomy of a Django/Daphne Access Log` --references--> `CorrelationIdMiddleware`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/middleware.py
- `Worker Leases, Fencing Tokens & Heartbeats` --references--> `StaleLeaseOwnershipError`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/services/catalogue_queue.py
- `HTTP 403 Forbidden` --references--> `transition_movie_classification()`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/services/movie_mutations.py
- `2. Secret Redaction Filter (`core/logging.py`)` --references--> `SecretRedactionFilter`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/logging.py
- `Phase 3: Durable Taste Engine & Tombstone Anonymization` --references--> `UserTasteProfile`  [INFERRED]
  tasks/todo.md → backend/core/models.py

## Import Cycles
- None detected.

## Communities (189 total, 88 thin omitted)

### Community 0 - "StreamingFilterAuditTests"
Cohesion: 0.07
Nodes (3): _link_streaming_availability(), resolve_streaming_provider_ids(), StreamingFilterAuditTests

### Community 1 - "Defense-in-Depth Debugging Strategies"
Cohesion: 0.06
Nodes (30): Boundary Testing, Checkpoint: Layered debugging complete, Cleanup and teardown, Defense-in-Depth Debugging Strategies, Dependency isolation, Divide and Conquer, Hypothesis Testing Protocol, Input validation (+22 more)

### Community 2 - "guestProvisionCoordinator.ts"
Cohesion: 0.14
Nodes (19): posthog-js@^1.319.0, App(), AppRouter(), AuthRecoveryPrompt(), AuthRecoveryPromptProps, ProvisionContinuationScreen(), ProvisionContinuationScreenProps, provisionGuest() (+11 more)

### Community 3 - "HomePage.tsx"
Cohesion: 0.08
Nodes (29): CinemaAdmissionTicket(), CinemaAdmissionTicketProps, CinemaSalonPass(), CinemaSalonPassProps, CuratorsDoubleFeature(), CuratorsDoubleFeatureProps, DoubleFeatureResponse, FilmCard() (+21 more)

### Community 4 - "_make_movie"
Cohesion: 0.11
Nodes (5): DryRunImmutabilityTest, _guard_pass(), _make_movie(), _mock_tmdb_response(), TMDBVerificationPipelineTest

### Community 5 - "apiRequest"
Cohesion: 0.05
Nodes (51): 1. The `ApiError` Class, 2. Automatic Error Message Extraction, 3. Automatic Session Expiration Handling (401 Interceptor), 4. Empty States vs. Actual Errors, Frontend Error Handling (`api.ts` & React), ApiError, apiRequest(), buildDeduplicationKey() (+43 more)

### Community 6 - "GuestConversionValidationAndRejectionTests"
Cohesion: 0.07
Nodes (3): GuestConversionRecoverySecurityTests, GuestConversionSuccessTests, GuestConversionValidationAndRejectionTests

### Community 8 - "DiscoverPage.tsx"
Cohesion: 0.07
Nodes (36): DeckCardSkeleton(), MatchItemSkeleton(), MovieCardSkeleton(), ShelfSkeleton(), Skeleton(), SkeletonProps, StreamingItemSkeleton(), usePrefersReducedMotion() (+28 more)

### Community 9 - "vitest"
Cohesion: 0.05
Nodes (36): SessionPage(), AvatarStack(), RecentSession, SessionCard(), SessionsListPage(), mockCuratorMovie, mockApiRequest, mockApiRequest (+28 more)

### Community 11 - "HardConstraints"
Cohesion: 0.07
Nodes (5): CandidatePool, HardConstraints, ManifestPrioritizationTests, ManifestLearnedFeedbackIntegrationTests, ReproducibilityAndPersistenceTests

### Community 12 - "tmdb.py"
Cohesion: 0.03
Nodes (24): broadcast_credential_revocation(), Command, MovieTagRelation, Meta, RegisterSerializer, Meta, IndianCatalogueCoverageReport, IndianCatalogueDiscoveryService (+16 more)

### Community 13 - "BottomNav"
Cohesion: 0.09
Nodes (30): BottomNav(), BottomNavProps, NavTab, CinemaHeader(), CinemaHeaderProps, CreateSessionPage(), autoInitSession(), createSession() (+22 more)

### Community 14 - "run_staleness_sweep"
Cohesion: 0.07
Nodes (5): StalenessSweepCheckpoint, Meta, run_staleness_sweep(), StalenessSweepService, StalenessSweepTests

### Community 15 - "tutorialSystem.test.tsx"
Cohesion: 0.10
Nodes (29): ThemeProvider(), ANON_ID_STORAGE_KEY, formatTourStorageKey(), generateAnonymousId(), getOrCreateAnonymousBrowserId(), getTourStatus(), getTourStorageKey(), hasSeenTour() (+21 more)

### Community 18 - "SessionPage.tsx"
Cohesion: 0.05
Nodes (49): CurtainCallMatchModal(), CurtainCallMatchModalProps, MatchMovie, MatchPresentationStyle, resolveMatchStyle(), baseMockMovie, MOTION_PROPS, ComputedLayout (+41 more)

### Community 19 - "compilerOptions"
Cohesion: 0.09
Nodes (21): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+13 more)

### Community 20 - "ConstraintExhaustionNoticeModal.tsx"
Cohesion: 0.13
Nodes (20): ErrorBoundary, Props, State, ConstraintExhaustionNoticeModal(), ConstraintExhaustionNoticeModalProps, ConstraintProposalData, DecisionInfo, parseDecision() (+12 more)

### Community 22 - "WebSocketRevocationTests"
Cohesion: 0.07
Nodes (7): WebSocketRevocationTests, run(), run(), run(), run(), run(), run()

### Community 23 - "UserPreferenceData"
Cohesion: 0.04
Nodes (8): ManifestCompilerService, UserPreferenceData, DeckStateConcurrencyTests, BoutiqueManifestCompilationTests, NormalManifestCompilationTests, ShortageRedistributionAndFloorTests, Phase1EndToEndScenarioTestCase, RoomRecommendationScenariosTestCase

### Community 26 - "permissions.py"
Cohesion: 0.17
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
Cohesion: 0.10
Nodes (3): set_redis_client(), TMDBRateLimiterProductionFailClosedTests, TMDBRateLimiterRedisLuaMockTests

### Community 33 - "Systematic Debugging"
Cohesion: 0.12
Nodes (15): Do not use this skill when, Examples, First move, Guardrails, Inputs to gather, Outputs, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis (+7 more)

### Community 34 - "manifest.json"
Cohesion: 0.12
Nodes (16): background_color, categories, description, display, icons, lang, name, orientation (+8 more)

### Community 36 - "CatalogueJob"
Cohesion: 0.09
Nodes (9): reset_handlers(), CatalogueJob, JobType, Meta, Status, handle_full_reconciliation(), handle_sync_changes_feed(), to_json_safe() (+1 more)

### Community 37 - ".record_swipe_response"
Cohesion: 0.04
Nodes (5): submit_duplicate(), submit_guest(), submit_host(), submit_swipe(), SuperLikeReactionMatrixIntegrationTests

### Community 39 - "IntelligenceWorkerProcess"
Cohesion: 0.06
Nodes (4): Command, IntelligenceWorkerProcess, register_handler(), IntelligenceWorkerTasteHandlerTests

### Community 40 - "backend/package.json"
Cohesion: 0.36
Nodes (7): devDependencies, autoprefixer@^10.4.23, postcss@^8.5.6, tailwindcss@^4.1.18, tailwindcss, autoprefixer, postcss

### Community 41 - "trackEvent"
Cohesion: 0.24
Nodes (18): trackEvent(), prefersReducedMotion(), AutoJoin(), join(), normalizeDeckCard(), preloadPoster(), SessionPageInner(), cleanupSocket() (+10 more)

### Community 43 - "_get_tmdb_request_headers"
Cohesion: 0.11
Nodes (17): _fetch(), format_tmdb_movie(), get_now_playing_movies(), _fetch(), get_popular_movies(), _fetch(), _get_tmdb_request_headers(), get_top_rated_movies() (+9 more)

### Community 44 - "test_seed_local_dev_catalogue.py"
Cohesion: 0.12
Nodes (7): _assert_safe_local_database(), _resolve_canonical_db_path(), LimitValidationTest, QueueLifecycleAndProvenanceCorrectionTest, SafetyGuardDebugFalseTest, SafetyGuardEngineTest, SafetyGuardPathTest

### Community 47 - "core/urls.py"
Cohesion: 0.03
Nodes (38): Session, SessionSerializer, Meta, DeckCardDeliveryView, DeleteAccountView, GenreListView, GenreSyncTMDBView, GuestRecoverView (+30 more)

### Community 50 - ".agent/skills/ui-ux-pro-max/scripts/design_system.py"
Cohesion: 0.14
Nodes (8): _detect_page_type(), format_ascii_box(), format_markdown(), format_master_md(), format_page_override_md(), generate_design_system(), _generate_intelligent_overrides(), persist_design_system()

### Community 51 - "router.tsx"
Cohesion: 0.06
Nodes (71): AccountSettingsPage, AnimatedRoutes(), AutoJoin, CreateSessionPage, DiscoverPage, EntryPage, ForgotPasswordPage, GuestConvertPage (+63 more)

### Community 53 - "merge_guest_activity"
Cohesion: 0.05
Nodes (17): is_taste_profile_customized(), reap_abandoned_guests(), merge_guest_activity(), MergeConflictError, MergeInputError, normalize_pair(), AbandonedGuestReaperTests, FrictionlessOnboardingConcurrencyTests (+9 more)

### Community 54 - "scripts"
Cohesion: 0.33
Nodes (6): scripts, build, dev, lint, preview, test

### Community 56 - "2xx — Successful Responses"
Cohesion: 0.13
Nodes (15): 2xx — Successful Responses, 3. Complete HTTP Status Code Guide, 3xx — Redirection & Caching, 5xx — Server-Side & Upstream Errors, HTTP 200 OK, HTTP 201 Created, HTTP 202 Accepted, HTTP 204 No Content (+7 more)

### Community 57 - "React + TypeScript + Vite"
Cohesion: 0.50
Nodes (3): Expanding the ESLint configuration, React Compiler, React + TypeScript + Vite

### Community 59 - "Phase6BatchCRecentSessionsAndStreamingTests"
Cohesion: 0.08
Nodes (6): _create_tmdb_session(), get_tmdb_session(), reset_tmdb_session(), Phase6BatchCRecentSessionsAndStreamingTests, Phase6BatchCTMDBReliabilityTests, worker()

### Community 60 - "flick-frontend/package.json"
Cohesion: 0.18
Nodes (10): @types/canvas-confetti@^1.9.0, @types/node@^24.10.1, typescript@~5.9.3, name, private, type, version, @types/canvas-confetti (+2 more)

### Community 61 - "evaluate_eligibility_predicates"
Cohesion: 0.08
Nodes (6): validate_movie_language(), evaluate_eligibility_predicates(), movie_genres_changed_handler(), register_eligibility_signals(), EligibilityPredicatesOptionBTests, LanguageValidationTests

### Community 62 - "LocalizedGenreRetrievalTests"
Cohesion: 0.11
Nodes (3): LocalizedGenreRetrievalTests, fake_ingest(), fake_ingest()

### Community 64 - "CatalogueQueueService"
Cohesion: 0.05
Nodes (6): _beat(), CatalogueQueueError, CatalogueQueueService, JobNotFoundError, StaleLeaseOwnershipError, CatalogueQueueUnitTests

### Community 67 - "acquire_tmdb_token"
Cohesion: 0.09
Nodes (3): acquire_tmdb_token(), reset_rate_limiter(), TMDBRateLimiterInMemoryTests

### Community 69 - "tmdb_rate_limiter.py"
Cohesion: 0.15
Nodes (8): calculate_cooldown_with_jitter(), get_rate_limiter_status(), get_redis_client(), is_production(), record_tmdb_429(), _redis_eval_acquire(), _redis_eval_record_429(), _redis_eval_status()

### Community 70 - "HistoricalReconciliationService"
Cohesion: 0.09
Nodes (10): HistoricalReconciliationService, map_swipe_reaction(), reconcile_historical_interactions(), HistoricalReconciliationServiceTests, Task 3: Historical Interaction Reconciliation Service & Command, Batch 4: Historical Interaction Reconciliation & Identity Linking — Task List, Checkpoint 2: Reconciliation & Identity Complete, Checkpoint 3: Batch 4 Complete (+2 more)

### Community 72 - "TmdbChangesService"
Cohesion: 0.06
Nodes (10): Command, TmdbChangesCheckpoint, Meta, poll_tmdb_changes(), PollerLockedError, RateLimitBackoffError, StalePollerOwnershipError, TmdbChangesService (+2 more)

### Community 74 - "devDependencies"
Cohesion: 0.14
Nodes (13): devDependencies, jsdom@^30.1.3, tailwindcss@^4.1.18, @testing-library/jest-dom@^7.0.1, @testing-library/react@^16.3.3, @types/react@^19.2.5, @types/react-dom@^19.2.3, vitest@^5.1.0 (+5 more)

### Community 79 - "9. Practical Troubleshooting Playbook"
Cohesion: 0.12
Nodes (17): 10. `502 Bad Gateway`, 11. `503 Service Unavailable`, 12. `504 Gateway Timeout`, 13. `ConnectionResetError(54, 'Connection reset by peer')`, 14. `ECONNREFUSED 127.0.0.1:8000`, 15. `AbortError: The operation was aborted`, 16. `CatalogueJob status = failed_permanent`, 1. `200 55` (+9 more)

### Community 80 - ".agents/skills/ui-ux-pro-max/scripts/core.py"
Cohesion: 0.23
Nodes (5): detect_domain(), _load_csv(), search(), _search_csv(), search_stack()

### Community 81 - "MovieSerializer"
Cohesion: 0.12
Nodes (6): MovieSerializer, Meta, MovieCreateView, MovieDetailView, MovieUpdateView, CompleteCatalogueView

### Community 83 - "InteractionLog"
Cohesion: 0.04
Nodes (43): InteractionLog, Meta, MovieExposure, MovieKeyword, MovieTag, Swipe, Meta, UserIdentityLink (+35 more)

### Community 84 - "ui-ux-pro-max"
Cohesion: 0.07
Nodes (29): Accessibility, Available Domains, Available Stacks, Common Rules for Professional UI, Example Workflow, How to Use This Skill, Icons & Visual Elements, Interaction (+21 more)

### Community 86 - "ProposalExecutionWorker"
Cohesion: 0.13
Nodes (3): Command, ProposalExecutionWorker, ProposalOutboxProcessBatchView

### Community 88 - "Session"
Cohesion: 0.06
Nodes (21): SessionOccasionState, calculate_questionnaire_similarity(), calculate_screening_affinity(), calculate_session_statistics(), calculate_taste_compatibility(), normalize_user_preferences(), ActiveManifestImmutableError, HamiltonManifestAllocator (+13 more)

### Community 90 - ".authenticate"
Cohesion: 0.12
Nodes (3): EmailOrUsernameModelBackend, AuthenticationLoggingSecurityTests, LoginView

### Community 91 - "PostgreSQLQueueConcurrencyTests"
Cohesion: 0.12
Nodes (3): PostgreSQLQueueConcurrencyTests, do_enqueue(), worker_task()

### Community 92 - "ui-ux-pro-max"
Cohesion: 0.07
Nodes (29): Accessibility, Available Domains, Available Stacks, Common Rules for Professional UI, Example Workflow, How to Use This Skill, Icons & Visual Elements, Interaction (+21 more)

### Community 93 - ".agents/skills/ui-ux-pro-max/scripts/design_system.py"
Cohesion: 0.14
Nodes (8): _detect_page_type(), format_ascii_box(), format_markdown(), format_master_md(), format_page_override_md(), generate_design_system(), _generate_intelligent_overrides(), persist_design_system()

### Community 95 - "tests.py"
Cohesion: 0.03
Nodes (14): ConcurrencyAndAtomicityTests, DiscoverTests, EmailVerificationTests, GenreIntegrationTests, LocalNetworkConfigurationTests, PaginationAndResourceLimitTests, RecentSessionsTests, RecommendationDiscoveryTests (+6 more)

### Community 98 - "models.py"
Cohesion: 0.06
Nodes (19): Command, Command, Command, Command, ConstraintExpansionProposal, Meta, Genre, MovieManager (+11 more)

### Community 99 - "GuestSecurityCryptoTests"
Cohesion: 0.05
Nodes (4): calculate_entropy_bits(), GuestSecurityCryptoTests, GuestSecurityDeploymentSettingsTests, GuestSecurityHMACAndVerificationTests

### Community 101 - "production_settings.py"
Cohesion: 0.16
Nodes (3): scrub_sentry_event(), scrub_value(), SentryScrubberTests

### Community 102 - "UserPreferenceData"
Cohesion: 0.06
Nodes (4): rank_candidates_for_user(), IndividualRelevanceScorer, MovieIntelligenceData, ScoringServiceTestCase

### Community 104 - "GuestProfile"
Cohesion: 0.03
Nodes (21): canonicalize_recovery_code(), compute_recovery_lookup_digest(), dummy_verify_recovery_code(), generate_recovery_code(), get_recovery_hmac_key(), hash_recovery_code(), verify_recovery_code(), GuestProfile (+13 more)

### Community 106 - "admin.py"
Cohesion: 0.20
Nodes (11): CustomUserAdmin, GenreAdmin, MatchAdmin, MovieAdmin, MovieStreamingAvailabilityAdmin, SessionAdmin, SessionStatsAdmin, StreamingProviderAdmin (+3 more)

### Community 107 - "test_observability_and_security.py"
Cohesion: 0.16
Nodes (5): CorrelationIdFilter, SecretRedactionFormatter, CorrelationIdConcurrencyTests, async_view(), __init__()

### Community 109 - "enrichment_handlers.py"
Cohesion: 0.11
Nodes (11): recalculate_movie_eligibility(), acquire_tmdb_token(), check_deterministic_identity(), handle_catalogue_classification(), handle_catalogue_enrichment(), is_synthetic_movie(), normalize_title(), record_tmdb_429() (+3 more)

### Community 110 - "WatchlistBatchAPITests"
Cohesion: 0.12
Nodes (3): create_test_movies(), DoubleFeatureAPITests, WatchlistBatchAPITests

### Community 113 - "SessionExpandConstraintsView"
Cohesion: 0.16
Nodes (4): ConstraintExpansionProposalSerializer, Meta, ProposalListCreateView, SessionExpandConstraintsView

### Community 115 - "Workflow Phases (Summary)"
Cohesion: 0.25
Nodes (7): Common Rationalisations, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis, Phase 3: Hypothesis and Testing, Phase 4: Implementation, Phases, Red Flags, and Common Rationalisations, Workflow Phases (Summary)

### Community 116 - "throttling.py"
Cohesion: 0.19
Nodes (6): AuthRateThrottle, GuestProvisionThrottle, GuestRecoverThrottle, GuestRecoveryKeyThrottle, PasswordResetRateThrottle, HTTP 429 Too Many Requests

### Community 117 - "CorrelationIdMiddlewareTests"
Cohesion: 0.10
Nodes (4): reset_correlation_id(), set_correlation_id(), CorrelationIdMiddleware, CorrelationIdMiddlewareTests

### Community 119 - "GuestProvisioningAPITests"
Cohesion: 0.09
Nodes (3): ExistingRegisteredUserCompatibilityTests, GuestProvisioningAPITests, GuestThrottlingTests

### Community 120 - "ProposalDecideView"
Cohesion: 0.15
Nodes (9): ProposalError, ProposalExpiredError, ProposalInvalidStateError, ProposalNotFoundError, ProposalPermissionDeniedError, ProposalSupersededError, ProposalApproveView, ProposalDecideView (+1 more)

### Community 123 - "eslint.config.js"
Cohesion: 0.15
Nodes (12): eslint@^9.39.1, @eslint/js@^9.39.1, eslint-plugin-react-hooks@^7.0.1, eslint-plugin-react-refresh@^0.4.24, globals@^16.5.0, typescript-eslint@^8.46.4, eslint, @eslint/js (+4 more)

### Community 127 - "dependencies"
Cohesion: 0.17
Nodes (12): dependencies, canvas-confetti@^1.9.4, framer-motion@^12.31.0, lucide-react@^0.577.0, material-symbols@^0.40.2, react@^19.2.0, react-dom@^19.2.0, react-router-dom@^7.12.0 (+4 more)

### Community 134 - "batch_sync_prelaunch.py"
Cohesion: 0.31
Nodes (3): Command, _make_session(), _tmdb_get()

### Community 137 - "interface"
Cohesion: 0.33
Nodes (5): interface, display_name, short_description, policy, allow_implicit_invocation

### Community 139 - "Examples"
Cohesion: 0.40
Nodes (4): Example 1: Test failure with stack trace, Example 2: Intermittent test failure, Example 3: Regression after a commit, Examples

### Community 140 - "Movie"
Cohesion: 0.08
Nodes (11): Movie, WatchlistItem, Meta, DoubleFeatureService, _movie_contains(), _movie_get(), _movie_getitem(), PersonalizedRecommendationEngine (+3 more)

### Community 141 - ".agent/skills/ui-ux-pro-max/scripts/core.py"
Cohesion: 0.22
Nodes (5): detect_domain(), _load_csv(), search(), _search_csv(), search_stack()

### Community 143 - "Session"
Cohesion: 0.06
Nodes (13): CollaborativeAgreement, SessionStats, ConflictingResponseError, DeckAdvancementService, DeckStateError, InvalidCardIndexError, OutOfOrderResponseError, StaleManifestError (+5 more)

### Community 157 - "Match"
Cohesion: 0.08
Nodes (5): Match, Meta, SuperLikePersistenceAndAttributionTests, compute_session_statistics(), serialize_session_matches()

### Community 158 - "5. Deep Dive: HTTP 304 Not Modified & Caching"
Cohesion: 0.40
Nodes (5): 5. Deep Dive: HTTP 304 Not Modified & Caching, Conditional Requests (ETag & Last-Modified), How Browser Caching Works, How Caching Is Implemented in Flick, When 304 Is Healthy vs When It Is a Problem

### Community 162 - "_validate_candidate"
Cohesion: 0.17
Nodes (4): _build_candidate_queryset(), Command, _validate_candidate(), CandidatePrevalidationTest

### Community 165 - "vite.config.ts"
Cohesion: 0.22
Nodes (6): @tailwindcss/vite@^4.1.18, vite@^7.2.4, @vitejs/plugin-react@^5.1.1, @tailwindcss/vite, vite, @vitejs/plugin-react

### Community 167 - "4xx — Client-Side Errors"
Cohesion: 0.18
Nodes (11): 4xx — Client-Side Errors, HTTP 400 Bad Request, HTTP 401 Unauthorized, HTTP 403 Forbidden, HTTP 404 Not Found, HTTP 405 Method Not Allowed, HTTP 408 Request Timeout, HTTP 409 Conflict (+3 more)

### Community 168 - "TokenAuthMiddleware"
Cohesion: 0.29
Nodes (3): get_user_from_token_key(), TokenAuthMiddleware, TokenAuthMiddlewareStack()

### Community 169 - "get_correlation_id"
Cohesion: 0.31
Nodes (4): get_correlation_id(), run_all(), worker(), failing_view()

### Community 170 - "MovieListView"
Cohesion: 0.33
Nodes (3): StandardResultsSetPagination, SwipeHistoryPagination, MovieListView

### Community 171 - "get_movie_by_tmdb_id"
Cohesion: 0.29
Nodes (4): get_enhanced_movie_details(), get_movie_by_tmdb_id(), _fetch(), get_movie_genres()

### Community 172 - "SecretRedactionFilter"
Cohesion: 0.19
Nodes (6): SecretRedactionFilter, 1. Custom Exception Handler (`backend/backend/exceptions.py`), 2. Secret Redaction Filter (`core/logging.py`), 3. Request Correlation ID Middleware (`core/middleware.py`), 6. Flick-Specific Error Handling Architecture, Backend Error Handling (DRF, Exceptions & Middleware)

### Community 177 - "SessionChemistry"
Cohesion: 0.17
Nodes (6): SessionChemistry, Meta, SwipeSerializer, Meta, _safe_analytics_callback(), _update_analytics_after_commit()

### Community 178 - "Flick — HTTP Status Codes, Server Logs & Error-Handling Reference"
Cohesion: 0.13
Nodes (14): 10. Glossary of Key Technical Terms, 1. Quick-Reference Cheat Sheet, 2. What Are HTTP Status Codes?, 7. Background Queue & Worker Numbers, 8. Frontend & Build-Related Numbers, At a Glance: What Do These Numbers Mean?, Flick — HTTP Status Codes, Server Logs & Error-Handling Reference, Port Numbers (+6 more)

### Community 179 - "CorrectSyntheticM1RecordsTest"
Cohesion: 0.12
Nodes (5): Command, _inspect_target_records(), _resolve_staff_user(), CorrectSyntheticM1RecordsTest, _guard_pass()

### Community 180 - "verify-batch-b-browser.js"
Cohesion: 0.21
Nodes (5): puppeteer-core@^25.16.0, SCREENSHOT_DIR, SCREENSHOT_DIR, SCREENSHOT_DIR, puppeteer-core

### Community 204 - "4. Deciphering Server Logs & Trailing Numbers"
Cohesion: 0.29
Nodes (7): 4. Deciphering Server Logs & Trailing Numbers, Anatomy of a Django/Daphne Access Log, What Do the Trailing Numbers Mean? (The 55 vs 1989 Mystery), Why does `/api/curators-selection/` show `200 1989`?, Why does `/api/users/profile/` show `200 55`?, Why does `GET /api/movies/` show `304 -` or `304 0`?, WSGI vs ASGI Logging Differences

### Community 209 - "fetch_cached_tmdb"
Cohesion: 0.15
Nodes (6): fetch_cached_tmdb(), RedisRateLimiterUnavailableError, 1. The Movie Database (TMDB), 2. Redis, 3. PostgreSQL & SQLite, External Service Failure Modes (TMDB, Redis, Postgres)

## Knowledge Gaps
- **88 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Movie` connect `Movie` to `StreamingFilterAuditTests`, `DeckStateAPITests`, `Phase6BatchBBackendTests`, `SwipeAndMatchingTests`, `ProposalLifecycleAndIdempotencyTestCase`, `_make_movie`, `batch_sync_prelaunch.py`, `TmdbChangesCheckpoint`, `SwipeFailureRecoveryAndEdgeCaseTests`, `HardConstraints`, `tmdb.py`, `run_staleness_sweep`, `Session`, `FunctionalAndMobileAuditVerificationTests`, `MovieQuerySetRestrictionTests`, `DoubleFeatureServiceTests`, `DatabaseConcurrencyAndSwipeReliabilityTests`, `UserPreferenceData`, `ClassicVaultEraFilterTests`, `SessionLifecycleAndQuestionnaireRecoveryTests`, `MotionAndSessionRegressionAuditTests`, `MovieMutationsTestCase`, `Match`, `IntelligenceModelsTestCase`, `_validate_candidate`, `CatalogueJob`, `.record_swipe_response`, `Stage3EndToEndProductValidationTests`, `IntelligenceWorkerProcess`, `MovieListView`, `_get_tmdb_request_headers`, `test_seed_local_dev_catalogue.py`, `ScreeningSessionResultsAndStatsPersistenceTests`, `MovieEligibilityModelAndSignalTests`, `AuthenticationAndPermissionTests`, `MatchListFilteringSecurityTests`, `core/urls.py`, `CorrectSyntheticM1RecordsTest`, `SessionChemistry`, `Command`, `merge_guest_activity`, `Phase6BatchCRecentSessionsAndStreamingTests`, `evaluate_eligibility_predicates`, `LocalizedGenreRetrievalTests`, `HardConstraintFilter`, `CatalogueQueueService`, `CandidateRetrievalAndEligibilityTests`, `HistoricalReconciliationService`, `TmdbChangesService`, `Batch5PersonalizationEvaluationTests`, `MovieSerializer`, `InteractionLog`, `UserTasteProfile`, `Session`, `SwipeUndoTests`, `PostgreSQLQueueConcurrencyTests`, `AffinityEvaluationTests`, `tests.py`, `.claim_jobs`, `models.py`, `UserPreferenceData`, `ArchiveShelvesService`, `GuestProfile`, `TestReliabilityAndRetrieval`, `admin.py`, `CoreUserExperienceRepairTests`, `enrichment_handlers.py`, `WatchlistBatchAPITests`, `InteractionLogProcessingStatusTests`, `DynamicMovieCatalogueTests`, `TestIngestionAndProvenance`, `Pre1990ReleasePeriodFilterTests`, `TestIndianLanguageDiscovery`?**
  _High betweenness centrality (0.237) - this node is a cross-community bridge._
- **Are the 138 inferred relationships involving `Movie` (e.g. with `Command` and `Command`) actually correct?**
  _`Movie` has 138 INFERRED edges - model-reasoned connections that need verification._
- **Should `StreamingFilterAuditTests` be split into smaller, more focused modules?**
  _Cohesion score 0.07407407407407407 - nodes in this community are weakly interconnected._
- **Why does `6. Flick-Specific Error Handling Architecture` connect `SecretRedactionFilter` to `fetch_cached_tmdb`, `Flick — HTTP Status Codes, Server Logs & Error-Handling Reference`, `apiRequest`?**
  _High betweenness centrality (0.191) - this node is a cross-community bridge._
- **Are the 86 inferred relationships involving `Session` (e.g. with `MatchConsumer` and `SessionDetailSerializer`) actually correct?**
  _`Session` has 86 INFERRED edges - model-reasoned connections that need verification._
- **Should `Defense-in-Depth Debugging Strategies` be split into smaller, more focused modules?**
  _Cohesion score 0.06451612903225806 - nodes in this community are weakly interconnected._
- **Why does `Frontend Error Handling (`api.ts` & React)` connect `apiRequest` to `SecretRedactionFilter`?**
  _High betweenness centrality (0.190) - this node is a cross-community bridge._