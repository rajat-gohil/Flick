# Graph Report - flick-app  (2026-11-18)

## Corpus Check
- 251 files · ~385,304 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 59 file(s) not represented in the graph (top: .csv 48, (none) 7, .example 2)

## Summary
- 4323 nodes · 9422 edges · 179 communities (96 shown, 83 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 1049 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `da6ef94d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ProfilePage.tsx
- Defense-in-Depth Debugging Strategies
- compute_recovery_lookup_digest
- django_db
- _make_movie
- router.tsx
- GuestConversionValidationAndRejectionTests
- WebSocketAuthenticationAndAuthorizationTests
- DiscoverPage.tsx
- apiRequest
- CatalogueJob
- TmdbChangesServiceTests
- PreferencesPage.tsx
- CinemaHeader
- run_staleness_sweep
- tutorialSystem.test.tsx
- DynamicMovieCatalogueTests
- Pre1990ReleasePeriodFilterTests
- SessionPage.tsx
- compilerOptions
- dependencies
- SessionQueryOptimizationTests
- WebSocketRevocationTests
- test_proposals.py
- ClassicVaultEraFilterTests
- SessionLifecycleAndQuestionnaireRecoveryTests
- permissions.py
- transition_movie_classification
- acquire_tmdb_token
- Root Cause Tracing Techniques
- compilerOptions
- TestReliabilityAndRetrieval
- MatchConsumer
- Systematic Debugging
- manifest.json
- ProposalAPITestCase
- GuestProfile
- Stage3EndToEndProductValidationTests
- Batch5PersonalizationEvaluationTests
- StreamingFilterAuditTests
- backend/package.json
- models.py
- views.py
- Phase6BatchCRecentSessionsAndStreamingTests
- GuestSecurityCryptoTests
- ScreeningSessionResultsAndStatsPersistenceTests
- DesignSystemGenerator
- core/urls.py
- .link_guest_to_user
- batch_sync_prelaunch.py
- .agent/skills/ui-ux-pro-max/scripts/design_system.py
- TestCase
- DesignSystemGenerator
- SwipeFailureRecoveryAndEdgeCaseTests
- scripts
- SecretRedactionFilter
- 3. Complete HTTP Status Code Guide
- React + TypeScript + Vite
- vercel.json
- tmdb.py
- GuestProvisioningAPITests
- evaluate_eligibility_predicates
- tmdb_rate_limiter.py
- sw.js
- models.py
- ProposalExecutionWorker
- tsconfig.json
- calculate_preference_score
- GuestActivityTrackingTests
- GuestSecurityHMACAndVerificationTests
- compute_session_statistics
- test_recommendation_evaluation.py
- .agent/skills/ui-ux-pro-max/scripts/core.py
- _assert_safe_local_database
- flick-frontend/package.json
- 9. Practical Troubleshooting Playbook
- GuestActivityMiddleware
- ArchiveShelvesService
- ui-ux-pro-max
- UserTasteProfile
- UserIdentityLinkModelTests
- HardConstraints
- CorrelationIdMiddleware
- .authenticate
- PostgreSQLQueueConcurrencyTests
- ui-ux-pro-max
- .agents/skills/ui-ux-pro-max/scripts/design_system.py
- UserPreferenceData
- UserIdentityLink
- set_redis_client
- CoreUserExperienceRepairTests
- .agent/skills/ui-ux-pro-max/scripts/search.py
- AuthenticationThrottlingTests
- .compile_manifest
- SuperLikePersistenceAndAttributionTests
- _validate_candidate
- UniversalLocalNetworkDevConfigurationTests
- admin.py
- .enqueue
- _tmdb_get
- SessionDetailSerializer
- InteractionLogProcessingStatusTests
- AdminCommandSecurityTests
- SessionPage.tsx
- Workflow Phases (Summary)
- AuthenticationAndPermissionTests
- Phase1EndToEndScenarioTestCase
- SettingsSecurityTests
- StalePollerOwnershipError
- PasswordResetSecurityTests
- eslint.config.js
- diagnose_lan_connectivity.sh
- HardConstraintFilter
- SessionJoiningTests
- ConstraintExpansionProposal
- Phase6BatchBBackendTests
- SwipeAndMatchingTests
- LimitValidationTest
- SessionCodeCollisionTests
- 2xx — Successful Responses
- _get_tmdb_request_headers
- TmdbChangesService
- devDependencies
- interface
- GuestRecoveryAPITests
- Examples
- partnerWaitingBehavior.test.tsx
- GuestRecoveryAPITests
- EmailVerificationTests
- trackEvent
- HealthCheckView
- AuthRateThrottle
- .record_swipe_response
- 7. Background Queue & Worker Numbers
- DiscoverTests
- MatchListFilteringSecurityTests
- GuestConversionConcurrencyTests
- MotionAndSessionRegressionAuditTests
- vite.config.ts
- get_correlation_id
- 4xx — Client-Side Errors
- reset_correlation_id
- SessionHistoryTests
- PaginationAndResourceLimitTests
- GuestProfileModelTests
- GuestRecoveryConcurrencyTests
- WatchlistTests
- .handle
- vercel.json
- Flick — HTTP Status Codes, Server Logs & Error-Handling Reference
- CorrectSyntheticM1RecordsTest
- verify-batch-b-browser.js
- CorrelationIdConcurrencyTests
- RecoveryHandoffReliabilityTests
- PollTmdbChangesCommandTests
- RecommendationDiscoveryTests
- parse_retry_after
- 5. Deep Dive: HTTP 304 Not Modified & Caching
- .test_concurrent_http_asgi_requests_through_middleware
- InteractionLog
- 4. Deciphering Server Logs & Trailing Numbers
- TestIndianLanguageDiscovery
- .handle
- IntelligenceModelsTestCase
- WatchlistItem
- InMemoryTokenBucket
- SecretRedactionFilter
- DatabaseConcurrencyAndSwipeReliabilityTests
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
- `Anatomy of a Django/Daphne Access Log` --references--> `CorrelationIdMiddleware`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/middleware.py
- `Worker Leases, Fencing Tokens & Heartbeats` --references--> `StaleLeaseOwnershipError`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/services/catalogue_queue.py
- `Task 4: Guest Identity Linking Service` --references--> `IdentityLinkingService`  [INFERRED]
  tasks/plan.md → backend/core/services/identity_linking.py
- `HTTP 403 Forbidden` --references--> `transition_movie_classification()`  [INFERRED]
  docs/HTTP_STATUS_AND_ERROR_HANDLING_GUIDE.md → backend/core/services/movie_mutations.py
- `Task 5: Durable Taste Engine Service & Job Handler` --references--> `TasteEngineService`  [INFERRED]
  tasks/plan.md → backend/core/services/taste_engine.py

## Import Cycles
- None detected.

## Communities (179 total, 83 thin omitted)

### Community 0 - "ProfilePage.tsx"
Cohesion: 0.15
Nodes (24): RecoveryCodeModal(), RecoveryCodeModalProps, identifyUser(), resetAnalyticsIdentity(), acknowledgeRecovery(), convertGuestAccount(), provisionGuest(), recoverGuest() (+16 more)

### Community 1 - "Defense-in-Depth Debugging Strategies"
Cohesion: 0.06
Nodes (30): Boundary Testing, Checkpoint: Layered debugging complete, Cleanup and teardown, Defense-in-Depth Debugging Strategies, Dependency isolation, Divide and Conquer, Hypothesis Testing Protocol, Input validation (+22 more)

### Community 2 - "compute_recovery_lookup_digest"
Cohesion: 0.11
Nodes (8): calculate_entropy_bits(), canonicalize_recovery_code(), compute_recovery_lookup_digest(), dummy_verify_recovery_code(), generate_recovery_code(), get_recovery_hmac_key(), hash_recovery_code(), verify_recovery_code()

### Community 3 - "django_db"
Cohesion: 0.03
Nodes (41): _inspect_target_records(), Migration, Migration, Migration, Migration, Migration, Migration, Migration (+33 more)

### Community 4 - "_make_movie"
Cohesion: 0.12
Nodes (4): DryRunImmutabilityTest, _guard_pass(), _make_movie(), TMDBVerificationPipelineTest

### Community 5 - "router.tsx"
Cohesion: 0.08
Nodes (39): App(), AccountSettingsPage, AnimatedRoutes(), AppRouter(), AutoJoin, CreateSessionPage, DiscoverPage, EntryPage (+31 more)

### Community 6 - "GuestConversionValidationAndRejectionTests"
Cohesion: 0.06
Nodes (4): GuestConversionDataIntegrityTests, GuestConversionRecoverySecurityTests, GuestConversionSuccessTests, GuestConversionValidationAndRejectionTests

### Community 8 - "DiscoverPage.tsx"
Cohesion: 0.06
Nodes (38): DeckCardSkeleton(), MatchItemSkeleton(), MovieCardSkeleton(), ShelfSkeleton(), Skeleton(), SkeletonProps, StreamingItemSkeleton(), Provider (+30 more)

### Community 9 - "apiRequest"
Cohesion: 0.08
Nodes (45): 1. The `ApiError` Class, 2. Automatic Error Message Extraction, 3. Automatic Session Expiration Handling (401 Interceptor), 4. Empty States vs. Actual Errors, Frontend Error Handling (`api.ts` & React), AuthShell(), generateUsernameSuggestions(), getPasswordStrength() (+37 more)

### Community 10 - "CatalogueJob"
Cohesion: 0.05
Nodes (22): Command, Command, register_handler(), reset_handlers(), CatalogueJob, JobType, Meta, Status (+14 more)

### Community 12 - "PreferencesPage.tsx"
Cohesion: 0.14
Nodes (14): OptionIcon(), PreferencesPage(), buildPreferences(), checkSessionState(), handleNext(), handleSubmit(), loadAuthoritativeState(), Question (+6 more)

### Community 13 - "CinemaHeader"
Cohesion: 0.11
Nodes (28): BottomNav(), BottomNavProps, NavTab, CinemaHeader(), CinemaHeaderProps, CreateSessionPage(), createSession(), Genre (+20 more)

### Community 14 - "run_staleness_sweep"
Cohesion: 0.05
Nodes (9): Command, StalenessSweepCheckpoint, Meta, handle_full_reconciliation(), handle_sync_changes_feed(), to_json_safe(), run_staleness_sweep(), StalenessSweepService (+1 more)

### Community 15 - "tutorialSystem.test.tsx"
Cohesion: 0.07
Nodes (46): SpotlightTour(), SpotlightTourStep, isLoggedIn(), ANON_ID_STORAGE_KEY, formatTourStorageKey(), generateAnonymousId(), getOrCreateAnonymousBrowserId(), getTourStatus() (+38 more)

### Community 16 - "DynamicMovieCatalogueTests"
Cohesion: 0.05
Nodes (3): DynamicMovieCatalogueTests, FunctionalAndMobileAuditVerificationTests, StreamingProviderAvailabilityTests

### Community 18 - "SessionPage.tsx"
Cohesion: 0.11
Nodes (26): ComputedLayout, computeTourLayout(), findVisibleTarget(), GestureHintCue(), getClampedTooltipWidth(), getViewportSize(), isFixedOrStickyElement(), isSameLayout() (+18 more)

### Community 19 - "compilerOptions"
Cohesion: 0.09
Nodes (21): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+13 more)

### Community 20 - "dependencies"
Cohesion: 0.15
Nodes (13): dependencies, canvas-confetti@^1.9.4, framer-motion@^12.31.0, lucide-react@^0.577.0, material-symbols@^0.40.2, posthog-js@^1.319.0, react@^19.2.0, react-dom@^19.2.0 (+5 more)

### Community 22 - "WebSocketRevocationTests"
Cohesion: 0.08
Nodes (8): broadcast_credential_revocation(), WebSocketRevocationTests, run(), run(), run(), run(), run(), run()

### Community 23 - "test_proposals.py"
Cohesion: 0.08
Nodes (9): ProposalError, ProposalExpiredError, ProposalInvalidStateError, ProposalNotFoundError, ProposalPermissionDeniedError, ProposalService, ProposalSupersededError, ProposalServiceTestCase (+1 more)

### Community 26 - "permissions.py"
Cohesion: 0.15
Nodes (4): configure_sqlite_pragmas(), CoreConfig, CoreConfig, IsOwner

### Community 27 - "transition_movie_classification"
Cohesion: 0.07
Nodes (4): transition_movie_classification(), update_movie_metadata(), _validate_field_provenance_updates(), MovieMutationsTestCase

### Community 28 - "acquire_tmdb_token"
Cohesion: 0.09
Nodes (3): acquire_tmdb_token(), reset_rate_limiter(), TMDBRateLimiterInMemoryTests

### Community 29 - "Root Cause Tracing Techniques"
Cohesion: 0.07
Nodes (26): Checkpoint: When investigation is complete, Common Root Cause Patterns, Component Boundary Tracing, Configuration mismatch, Data Flow Analysis, Diff-based investigation, Error Message Anatomy, Example: Wrong calculation (+18 more)

### Community 30 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+11 more)

### Community 31 - "TestReliabilityAndRetrieval"
Cohesion: 0.05
Nodes (8): get_movie_watch_providers(), TMDBAPIError, TMDBServiceError, TMDBTimeoutError, TestIngestionAndProvenance, TestReliabilityAndRetrieval, StreamingOptionsRemediationTests, MovieStreamingOptionsView

### Community 33 - "Systematic Debugging"
Cohesion: 0.12
Nodes (15): Do not use this skill when, Examples, First move, Guardrails, Inputs to gather, Outputs, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis (+7 more)

### Community 34 - "manifest.json"
Cohesion: 0.12
Nodes (16): background_color, categories, description, display, icons, lang, name, orientation (+8 more)

### Community 37 - "Stage3EndToEndProductValidationTests"
Cohesion: 0.06
Nodes (4): ConstraintExpansionProposal, Meta, Stage3EndToEndProductValidationTests, SessionResetPreferencesView

### Community 38 - "Batch5PersonalizationEvaluationTests"
Cohesion: 0.05
Nodes (6): MovieExposure, _movie_contains(), _movie_get(), _movie_getitem(), PersonalizedRecommendationEngine, _pluralize_genre()

### Community 40 - "backend/package.json"
Cohesion: 0.36
Nodes (7): devDependencies, autoprefixer@^10.4.23, postcss@^8.5.6, tailwindcss@^4.1.18, tailwindcss, autoprefixer, postcss

### Community 41 - "models.py"
Cohesion: 0.05
Nodes (33): CollaborativeAgreement, Match, Meta, Session, SessionStats, Swipe, Meta, ConflictingResponseError (+25 more)

### Community 42 - "views.py"
Cohesion: 0.04
Nodes (19): MovieTagRelation, Meta, StandardResultsSetPagination, SwipeHistoryPagination, RegisterSerializer, Meta, SwipeSerializer, Meta (+11 more)

### Community 43 - "Phase6BatchCRecentSessionsAndStreamingTests"
Cohesion: 0.09
Nodes (4): reset_tmdb_session(), Phase6BatchCRecentSessionsAndStreamingTests, Phase6BatchCTMDBReliabilityTests, worker()

### Community 47 - "core/urls.py"
Cohesion: 0.04
Nodes (24): DeckSwipeUndoView, DeleteAccountView, GenreSyncTMDBView, GuestConvertView, GuestProvisionView, GuestRecoverView, GuestRecoveryAckView, GuestRotateCodeView (+16 more)

### Community 48 - ".link_guest_to_user"
Cohesion: 0.14
Nodes (3): DuplicateIdentityLinkError, IdentityLinkingService, IdentityLinkingServiceTests

### Community 49 - "batch_sync_prelaunch.py"
Cohesion: 0.10
Nodes (5): fetch_tmdb_movies(), _create_tmdb_session(), get_tmdb_session(), _mock_tmdb_response(), QueueLifecycleAndProvenanceCorrectionTest

### Community 50 - ".agent/skills/ui-ux-pro-max/scripts/design_system.py"
Cohesion: 0.14
Nodes (8): _detect_page_type(), format_ascii_box(), format_markdown(), format_master_md(), format_page_override_md(), generate_design_system(), _generate_intelligent_overrides(), persist_design_system()

### Community 51 - "TestCase"
Cohesion: 0.08
Nodes (5): GenreIntegrationTests, LocalNetworkConfigurationTests, RecentSessionsTests, SessionLifecycleTests, WorkflowEndToEndIntegrationTests

### Community 54 - "scripts"
Cohesion: 0.33
Nodes (6): scripts, build, dev, lint, preview, test

### Community 55 - "SecretRedactionFilter"
Cohesion: 0.17
Nodes (6): SecretRedactionFilter, 1. Custom Exception Handler (`backend/backend/exceptions.py`), 2. Secret Redaction Filter (`core/logging.py`), 3. Request Correlation ID Middleware (`core/middleware.py`), 6. Flick-Specific Error Handling Architecture, Backend Error Handling (DRF, Exceptions & Middleware)

### Community 56 - "3. Complete HTTP Status Code Guide"
Cohesion: 0.20
Nodes (10): 3. Complete HTTP Status Code Guide, 3xx — Redirection & Caching, 5xx — Server-Side & Upstream Errors, HTTP 301 Moved Permanently, HTTP 302 Found / Temporary Redirect, HTTP 304 Not Modified, HTTP 500 Internal Server Error, HTTP 502 Bad Gateway (+2 more)

### Community 57 - "React + TypeScript + Vite"
Cohesion: 0.50
Nodes (3): Expanding the ESLint configuration, React Compiler, React + TypeScript + Vite

### Community 59 - "tmdb.py"
Cohesion: 0.04
Nodes (31): validate_movie_language(), Command, Movie, movie_genres_changed_handler(), recalculate_movie_eligibility(), register_eligibility_signals(), DiscoveryQuerySpec, IndianCatalogueCoverageReport (+23 more)

### Community 61 - "evaluate_eligibility_predicates"
Cohesion: 0.08
Nodes (5): MovieQuerySet, evaluate_eligibility_predicates(), EligibilityPredicatesOptionBTests, MovieEligibilityModelAndSignalTests, MovieQuerySetRestrictionTests

### Community 62 - "tmdb_rate_limiter.py"
Cohesion: 0.13
Nodes (9): calculate_cooldown_with_jitter(), get_rate_limiter_status(), get_redis_client(), is_production(), record_tmdb_429(), _redis_eval_acquire(), _redis_eval_record_429(), _redis_eval_status() (+1 more)

### Community 64 - "models.py"
Cohesion: 0.05
Nodes (19): Command, Command, Command, Command, get_user_from_token_key(), TokenAuthMiddleware, TokenAuthMiddlewareStack(), Genre (+11 more)

### Community 65 - "ProposalExecutionWorker"
Cohesion: 0.07
Nodes (6): Command, ProposalExecutionWorker, fake_ingest(), ProposalLifecycleAndIdempotencyTestCase, ProposalOutboxWorkerTestCase, ProposalOutboxProcessBatchView

### Community 71 - "test_recommendation_evaluation.py"
Cohesion: 0.07
Nodes (10): compute_cohort_divergence(), compute_negative_response_rate(), compute_preference_alignment(), compute_shelf_diversity(), compute_unexposed_discovery_ratio(), _extract_movie_id(), _extract_movie_tokens(), RecommendationEvaluationService (+2 more)

### Community 72 - ".agent/skills/ui-ux-pro-max/scripts/core.py"
Cohesion: 0.06
Nodes (12): BM25, detect_domain(), _load_csv(), search(), _search_csv(), search_stack(), BM25, detect_domain() (+4 more)

### Community 73 - "_assert_safe_local_database"
Cohesion: 0.21
Nodes (5): _assert_safe_local_database(), _resolve_canonical_db_path(), SafetyGuardDebugFalseTest, SafetyGuardEngineTest, SafetyGuardPathTest

### Community 74 - "flick-frontend/package.json"
Cohesion: 0.18
Nodes (10): tailwindcss@^4.1.18, @types/canvas-confetti@^1.9.0, @types/node@^24.10.1, tailwindcss, name, private, type, version (+2 more)

### Community 79 - "9. Practical Troubleshooting Playbook"
Cohesion: 0.12
Nodes (17): 10. `502 Bad Gateway`, 11. `503 Service Unavailable`, 12. `504 Gateway Timeout`, 13. `ConnectionResetError(54, 'Connection reset by peer')`, 14. `ECONNREFUSED 127.0.0.1:8000`, 15. `AbortError: The operation was aborted`, 16. `CatalogueJob status = failed_permanent`, 1. `200 55` (+9 more)

### Community 81 - "ArchiveShelvesService"
Cohesion: 0.10
Nodes (6): MovieSerializer, Meta, ArchiveShelvesService, CompleteCatalogueView, CuratorsSelectionView, YourArchiveView

### Community 84 - "ui-ux-pro-max"
Cohesion: 0.07
Nodes (29): Accessibility, Available Domains, Available Stacks, Common Rules for Professional UI, Example Workflow, How to Use This Skill, Icons & Visual Elements, Interaction (+21 more)

### Community 85 - "UserTasteProfile"
Cohesion: 0.09
Nodes (8): UserProfile, UserTasteProfile, TombstoneService, TombstoneServiceTests, DeleteAccountEndpointTests, Task 6: Privacy-Preserving Tombstone Anonymization, Checkpoint 3: Batch 4 Complete, Phase 3: Durable Taste Engine & Tombstone Anonymization

### Community 88 - "HardConstraints"
Cohesion: 0.03
Nodes (12): SessionOccasionState, CandidatePool, CandidateRetrievalService, compute_learned_feedback_from_logs(), FilmNoirClassifier, HardConstraints, WorldCinemaClassifier, LocalizedGenreRetrievalTests (+4 more)

### Community 91 - "PostgreSQLQueueConcurrencyTests"
Cohesion: 0.12
Nodes (3): PostgreSQLQueueConcurrencyTests, do_enqueue(), worker_task()

### Community 92 - "ui-ux-pro-max"
Cohesion: 0.07
Nodes (29): Accessibility, Available Domains, Available Stacks, Common Rules for Professional UI, Example Workflow, How to Use This Skill, Icons & Visual Elements, Interaction (+21 more)

### Community 93 - ".agents/skills/ui-ux-pro-max/scripts/design_system.py"
Cohesion: 0.14
Nodes (8): _detect_page_type(), format_ascii_box(), format_markdown(), format_master_md(), format_page_override_md(), generate_design_system(), _generate_intelligent_overrides(), persist_design_system()

### Community 94 - "UserPreferenceData"
Cohesion: 0.03
Nodes (21): GenreSerializer, Meta, SessionSerializer, Meta, calculate_questionnaire_similarity(), calculate_screening_affinity(), calculate_session_statistics(), calculate_taste_compatibility() (+13 more)

### Community 95 - "UserIdentityLink"
Cohesion: 0.04
Nodes (12): MovieKeyword, MovieTag, UserIdentityLink, LinkType, Meta, handle_recompute_taste_profile(), recompute_user_taste_profile(), TasteEngineService (+4 more)

### Community 96 - "set_redis_client"
Cohesion: 0.10
Nodes (3): set_redis_client(), TMDBRateLimiterProductionFailClosedTests, TMDBRateLimiterRedisLuaMockTests

### Community 99 - ".agent/skills/ui-ux-pro-max/scripts/search.py"
Cohesion: 0.10
Nodes (4): format_output(), format_output(), main(), start.sh script

### Community 102 - ".compile_manifest"
Cohesion: 0.09
Nodes (3): BoutiqueManifestCompilationTests, NormalManifestCompilationTests, ShortageRedistributionAndFloorTests

### Community 106 - "admin.py"
Cohesion: 0.20
Nodes (11): CustomUserAdmin, GenreAdmin, MatchAdmin, MovieAdmin, MovieStreamingAvailabilityAdmin, SessionAdmin, SessionStatsAdmin, StreamingProviderAdmin (+3 more)

### Community 108 - ".enqueue"
Cohesion: 0.03
Nodes (5): IntelligenceWorkerProcess, _beat(), Batch2EnrichmentAndWorkerTests, Batch3WorkerIntegrationTests, CatalogueQueueUnitTests

### Community 109 - "_tmdb_get"
Cohesion: 0.27
Nodes (3): Command, _make_session(), _tmdb_get()

### Community 114 - "SessionPage.tsx"
Cohesion: 0.06
Nodes (42): ErrorBoundary, Props, State, ConstraintExhaustionNoticeModal(), ConstraintExhaustionNoticeModalProps, ConstraintProposalData, DecisionInfo, parseDecision() (+34 more)

### Community 115 - "Workflow Phases (Summary)"
Cohesion: 0.25
Nodes (7): Common Rationalisations, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis, Phase 3: Hypothesis and Testing, Phase 4: Implementation, Phases, Red Flags, and Common Rationalisations, Workflow Phases (Summary)

### Community 118 - "Phase1EndToEndScenarioTestCase"
Cohesion: 0.07
Nodes (7): ProposalOutboxMessage, Meta, ProposalOutboxMessageSerializer, Meta, HamiltonManifestAllocator, HamiltonManifestAllocatorTests, Phase1EndToEndScenarioTestCase

### Community 121 - "StalePollerOwnershipError"
Cohesion: 0.18
Nodes (5): Command, PollerLockedError, RateLimitBackoffError, StalePollerOwnershipError, TmdbConfigError

### Community 123 - "eslint.config.js"
Cohesion: 0.15
Nodes (12): eslint@^9.39.1, @eslint/js@^9.39.1, eslint-plugin-react-hooks@^7.0.1, eslint-plugin-react-refresh@^0.4.24, globals@^16.5.0, typescript-eslint@^8.46.4, eslint, @eslint/js (+4 more)

### Community 127 - "ConstraintExpansionProposal"
Cohesion: 0.17
Nodes (4): ConstraintExpansionProposalSerializer, Meta, ProposalDetailView, ProposalListCreateView

### Community 133 - "2xx — Successful Responses"
Cohesion: 0.40
Nodes (5): 2xx — Successful Responses, HTTP 200 OK, HTTP 201 Created, HTTP 202 Accepted, HTTP 204 No Content

### Community 134 - "_get_tmdb_request_headers"
Cohesion: 0.27
Nodes (9): _fetch(), _fetch(), _fetch(), _fetch(), get_tmdb_genres(), _get_tmdb_request_headers(), _fetch(), _fetch() (+1 more)

### Community 136 - "devDependencies"
Cohesion: 0.14
Nodes (13): devDependencies, jsdom@^30.1.3, @testing-library/jest-dom@^7.0.1, @testing-library/react@^16.3.3, @types/react@^19.2.5, @types/react-dom@^19.2.3, typescript@~5.9.3, vitest@^5.1.0 (+5 more)

### Community 137 - "interface"
Cohesion: 0.33
Nodes (5): interface, display_name, short_description, policy, allow_implicit_invocation

### Community 139 - "Examples"
Cohesion: 0.40
Nodes (4): Example 1: Test failure with stack trace, Example 2: Intermittent test failure, Example 3: Regression after a commit, Examples

### Community 140 - "partnerWaitingBehavior.test.tsx"
Cohesion: 0.13
Nodes (13): AvatarStack(), RecentSession, SessionCard(), SessionsListPage(), guestSessionResponse, hostSessionData, hostSessionResponse, mockApiRequest (+5 more)

### Community 144 - "trackEvent"
Cohesion: 0.17
Nodes (21): trackEvent(), getWsBaseUrl(), getWsUrl(), prefersReducedMotion(), AutoJoin(), join(), JoinViaLink(), MovieSwipeCard (+13 more)

### Community 146 - "AuthRateThrottle"
Cohesion: 0.11
Nodes (8): AuthRateThrottle, GuestProvisionThrottle, GuestRecoverThrottle, PasswordResetRateThrottle, LoginView, PasswordResetRequestView, RegisterView, HTTP 429 Too Many Requests

### Community 147 - ".record_swipe_response"
Cohesion: 0.03
Nodes (5): submit_duplicate(), submit_guest(), submit_host(), submit_swipe(), SuperLikeReactionMatrixIntegrationTests

### Community 150 - "7. Background Queue & Worker Numbers"
Cohesion: 0.40
Nodes (5): 7. Background Queue & Worker Numbers, Queue Priorities & Fair Scheduling Quotas, Retry Limits, Exponential Backoff & Quarantine, TMDB Dual-Bucket Rate Limiter Constants, Worker Leases, Fencing Tokens & Heartbeats

### Community 165 - "vite.config.ts"
Cohesion: 0.22
Nodes (6): @tailwindcss/vite@^4.1.18, vite@^7.2.4, @vitejs/plugin-react@^5.1.1, @tailwindcss/vite, vite, @vitejs/plugin-react

### Community 166 - "get_correlation_id"
Cohesion: 0.31
Nodes (4): get_correlation_id(), run_all(), worker(), failing_view()

### Community 167 - "4xx — Client-Side Errors"
Cohesion: 0.18
Nodes (11): 4xx — Client-Side Errors, HTTP 400 Bad Request, HTTP 401 Unauthorized, HTTP 403 Forbidden, HTTP 404 Not Found, HTTP 405 Method Not Allowed, HTTP 408 Request Timeout, HTTP 409 Conflict (+3 more)

### Community 178 - "Flick — HTTP Status Codes, Server Logs & Error-Handling Reference"
Cohesion: 0.20
Nodes (9): 10. Glossary of Key Technical Terms, 1. Quick-Reference Cheat Sheet, 2. What Are HTTP Status Codes?, 8. Frontend & Build-Related Numbers, At a Glance: What Do These Numbers Mean?, Flick — HTTP Status Codes, Server Logs & Error-Handling Reference, Port Numbers, Table of Contents (+1 more)

### Community 179 - "CorrectSyntheticM1RecordsTest"
Cohesion: 0.15
Nodes (4): _resolve_staff_user(), _build_candidate_queryset(), CorrectSyntheticM1RecordsTest, _guard_pass()

### Community 180 - "verify-batch-b-browser.js"
Cohesion: 0.21
Nodes (5): puppeteer-core@^25.16.0, SCREENSHOT_DIR, SCREENSHOT_DIR, SCREENSHOT_DIR, puppeteer-core

### Community 196 - "5. Deep Dive: HTTP 304 Not Modified & Caching"
Cohesion: 0.40
Nodes (5): 5. Deep Dive: HTTP 304 Not Modified & Caching, Conditional Requests (ETag & Last-Modified), How Browser Caching Works, How Caching Is Implemented in Flick, When 304 Is Healthy vs When It Is a Problem

### Community 201 - "InteractionLog"
Cohesion: 0.05
Nodes (26): Command, InteractionLog, Meta, HistoricalReconciliationService, map_swipe_reaction(), reconcile_historical_interactions(), HistoricalReconciliationServiceTests, SwipeUndoViewInverseParityTests (+18 more)

### Community 204 - "4. Deciphering Server Logs & Trailing Numbers"
Cohesion: 0.29
Nodes (7): 4. Deciphering Server Logs & Trailing Numbers, Anatomy of a Django/Daphne Access Log, What Do the Trailing Numbers Mean? (The 55 vs 1989 Mystery), Why does `/api/curators-selection/` show `200 1989`?, Why does `/api/users/profile/` show `200 55`?, Why does `GET /api/movies/` show `304 -` or `304 0`?, WSGI vs ASGI Logging Differences

### Community 209 - "WatchlistItem"
Cohesion: 0.17
Nodes (4): WatchlistItem, Meta, WatchlistDetailView, WatchlistView

### Community 211 - "InMemoryTokenBucket"
Cohesion: 0.15
Nodes (5): InMemoryTokenBucket, 1. The Movie Database (TMDB), 2. Redis, 3. PostgreSQL & SQLite, External Service Failure Modes (TMDB, Redis, Postgres)

### Community 219 - "SecretRedactionFilter"
Cohesion: 0.12
Nodes (3): CorrelationIdFilter, SecretRedactionFormatter, SecretRedactionLoggerTests

## Knowledge Gaps
- **83 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Movie` connect `tmdb.py` to `Phase6BatchBBackendTests`, `SwipeAndMatchingTests`, `django_db`, `_make_movie`, `LimitValidationTest`, `GuestConversionValidationAndRejectionTests`, `TmdbChangesService`, `CatalogueJob`, `TmdbChangesServiceTests`, `run_staleness_sweep`, `DeckStateAPITests`, `Pre1990ReleasePeriodFilterTests`, `DynamicMovieCatalogueTests`, `.record_swipe_response`, `SessionQueryOptimizationTests`, `test_proposals.py`, `ClassicVaultEraFilterTests`, `SessionLifecycleAndQuestionnaireRecoveryTests`, `DiscoverTests`, `transition_movie_classification`, `MatchListFilteringSecurityTests`, `TestReliabilityAndRetrieval`, `MotionAndSessionRegressionAuditTests`, `Stage3EndToEndProductValidationTests`, `Batch5PersonalizationEvaluationTests`, `StreamingFilterAuditTests`, `models.py`, `SessionHistoryTests`, `Phase6BatchCRecentSessionsAndStreamingTests`, `PaginationAndResourceLimitTests`, `ScreeningSessionResultsAndStatsPersistenceTests`, `WatchlistTests`, `.handle`, `.link_guest_to_user`, `batch_sync_prelaunch.py`, `views.py`, `CorrectSyntheticM1RecordsTest`, `TestCase`, `SwipeFailureRecoveryAndEdgeCaseTests`, `core/urls.py`, `PollTmdbChangesCommandTests`, `RecommendationDiscoveryTests`, `evaluate_eligibility_predicates`, `models.py`, `ProposalExecutionWorker`, `test_recommendation_evaluation.py`, `InteractionLog`, `TestIndianLanguageDiscovery`, `.handle`, `IntelligenceModelsTestCase`, `ArchiveShelvesService`, `WatchlistItem`, `UserTasteProfile`, `HardConstraints`, `PostgreSQLQueueConcurrencyTests`, `UserPreferenceData`, `UserIdentityLink`, `CoreUserExperienceRepairTests`, `.compile_manifest`, `SuperLikePersistenceAndAttributionTests`, `_validate_candidate`, `admin.py`, `.enqueue`, `_tmdb_get`, `InteractionLogProcessingStatusTests`, `DatabaseConcurrencyAndSwipeReliabilityTests`, `AuthenticationAndPermissionTests`, `Phase1EndToEndScenarioTestCase`, `HardConstraintFilter`?**
  _High betweenness centrality (0.248) - this node is a cross-community bridge._
- **Are the 130 inferred relationships involving `Movie` (e.g. with `Command` and `Command`) actually correct?**
  _`Movie` has 130 INFERRED edges - model-reasoned connections that need verification._
- **Should `Defense-in-Depth Debugging Strategies` be split into smaller, more focused modules?**
  _Cohesion score 0.06451612903225806 - nodes in this community are weakly interconnected._
- **Why does `6. Flick-Specific Error Handling Architecture` connect `SecretRedactionFilter` to `apiRequest`, `Flick — HTTP Status Codes, Server Logs & Error-Handling Reference`, `InMemoryTokenBucket`?**
  _High betweenness centrality (0.163) - this node is a cross-community bridge._
- **Are the 79 inferred relationships involving `Session` (e.g. with `MatchConsumer` and `SessionDetailSerializer`) actually correct?**
  _`Session` has 79 INFERRED edges - model-reasoned connections that need verification._
- **Should `compute_recovery_lookup_digest` be split into smaller, more focused modules?**
  _Cohesion score 0.1140819964349376 - nodes in this community are weakly interconnected._
- **Why does `Frontend Error Handling (`api.ts` & React)` connect `apiRequest` to `SecretRedactionFilter`?**
  _High betweenness centrality (0.162) - this node is a cross-community bridge._