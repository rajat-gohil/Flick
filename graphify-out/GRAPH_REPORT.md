# Graph Report - flick-app  (2026-11-17)

## Corpus Check
- 249 files · ~376,073 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 59 file(s) not represented in the graph (top: .csv 48, (none) 7, .example 2)

## Summary
- 4263 nodes · 9231 edges · 183 communities (92 shown, 91 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 1049 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f21b3445`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Movie
- Defense-in-Depth Debugging Strategies
- compute_recovery_lookup_digest
- django_db
- _make_movie
- router.tsx
- GuestConversionValidationAndRejectionTests
- WebSocketAuthenticationAndAuthorizationTests
- DiscoverPage.tsx
- apiRequest
- PreferenceAndManifestCorrectnessTests
- tmdb_changes.py
- LocalizedGenreRetrievalTests
- CinemaHeader
- run_staleness_sweep
- Batch5PersonalizationEvaluationTests
- DynamicMovieCatalogueTests
- IntelligenceWorkerProcess
- SessionPage.tsx
- compilerOptions
- CatalogueJob
- Stage3EndToEndProductValidationTests
- WebSocketRevocationTests
- ProposalExecutionWorker
- Pre1990ReleasePeriodFilterTests
- SessionLifecycleAndQuestionnaireRecoveryTests
- permissions.py
- transition_movie_classification
- acquire_tmdb_token
- Root Cause Tracing Techniques
- compilerOptions
- RoomRecommendationScenariosTestCase
- MatchConsumer
- Systematic Debugging
- manifest.json
- ProposalAPITestCase
- GuestProfile
- UserPreferenceData
- .get_recommendations
- backend/package.json
- Genre
- calculate_preference_score
- UserProfile
- admin.py
- ScreeningSessionResultsAndStatsPersistenceTests
- DesignSystemGenerator
- views.py
- .link_guest_to_user
- enrichment_handlers.py
- .agent/skills/ui-ux-pro-max/scripts/design_system.py
- LocalNetworkConfigurationTests
- DesignSystemGenerator
- Batch2EnrichmentAndWorkerTests
- scripts
- 6. Flick-Specific Error Handling Architecture
- 3. Complete HTTP Status Code Guide
- React + TypeScript + Vite
- vercel.json
- tmdb.py
- .enqueue
- evaluate_eligibility_predicates
- tmdb_rate_limiter.py
- sw.js
- TMDBTimeoutError
- test_proposals.py
- tsconfig.json
- Session
- GuestActivityTrackingTests
- partnerWaitingBehavior.test.tsx
- Phase1EndToEndScenarioTestCase
- test_batch5_personalization.py
- .agent/skills/ui-ux-pro-max/scripts/core.py
- _assert_safe_local_database
- 9. Practical Troubleshooting Playbook
- .undo_card_response
- ArchiveShelvesService
- SuperLikeReactionMatrixIntegrationTests
- ui-ux-pro-max
- .anonymize_and_delete_user
- api.ts
- UserIdentityLinkModelTests
- HardConstraints
- TmdbChangesCheckpoint
- PasswordResetSecurityTests
- PostgreSQLQueueConcurrencyTests
- ui-ux-pro-max
- .agents/skills/ui-ux-pro-max/scripts/design_system.py
- UserIdentityLink
- set_redis_client
- DeckStateConcurrencyTests
- tests.py
- .agent/skills/ui-ux-pro-max/scripts/search.py
- AuthenticationThrottlingTests
- BoutiqueManifestCompilationTests
- SuperLikePersistenceAndAttributionTests
- _validate_candidate
- UniversalLocalNetworkDevConfigurationTests
- 7. Background Queue & Worker Numbers
- .calculate_allocation
- .from_movie
- Phase6BatchCRecentSessionsAndStreamingTests
- SessionDetailSerializer
- InteractionLogProcessingStatusTests
- StreamingProvider
- AdminCommandSecurityTests
- SessionPage.tsx
- Workflow Phases (Summary)
- Detailed Tasks
- IndividualRelevanceScorer
- .handle
- SettingsSecurityTests
- rank_candidates_for_user
- .handle
- handle_recompute_taste_profile
- diagnose_lan_connectivity.sh
- NormalManifestCompilationTests
- ShortageRedistributionAndFloorTests
- Phase6BatchBBackendTests
- SwipeAndMatchingTests
- middleware.py
- LimitValidationTest
- SessionCodeCollisionTests
- 2xx — Successful Responses
- MovieTagRelation
- flick-frontend/package.json
- interface
- Phase6BatchBConcurrencyTests
- Examples
- SwipeCreateView
- Batch 4: Historical Interaction Reconciliation & Identity Linking — Task List
- GuestRecoveryAPITests
- EmailVerificationTests
- PreferencesPage.tsx
- .test_concurrent_duplicate_submissions_race_condition
- MovieManager
- DiscoverTests
- Match
- MatchListFilteringSecurityTests
- AffinityEvaluationTests
- GuestConversionConcurrencyTests
- 4xx — Client-Side Errors
- DeckCardDeliveryView
- vercel.json
- Flick — HTTP Status Codes, Server Logs & Error-Handling Reference
- CorrectSyntheticM1RecordsTest
- verify-batch-b-browser.js
- parse_retry_after
- 5. Deep Dive: HTTP 304 Not Modified & Caching
- .reconcile
- 4. Deciphering Server Logs & Trailing Numbers
- test_indian_catalogue_ingestion.py
- IntelligenceModelsTestCase
- InMemoryTokenBucket
- test_observability_and_security.py
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

## Communities (183 total, 91 thin omitted)

### Community 0 - "Movie"
Cohesion: 0.05
Nodes (28): Movie, MovieExposure, MovieKeyword, MovieTag, Swipe, Meta, UserIdentityLink, LinkType (+20 more)

### Community 1 - "Defense-in-Depth Debugging Strategies"
Cohesion: 0.06
Nodes (30): Boundary Testing, Checkpoint: Layered debugging complete, Cleanup and teardown, Defense-in-Depth Debugging Strategies, Dependency isolation, Divide and Conquer, Hypothesis Testing Protocol, Input validation (+22 more)

### Community 2 - "compute_recovery_lookup_digest"
Cohesion: 0.04
Nodes (12): calculate_entropy_bits(), canonicalize_recovery_code(), compute_recovery_lookup_digest(), dummy_verify_recovery_code(), generate_recovery_code(), get_recovery_hmac_key(), hash_recovery_code(), verify_recovery_code() (+4 more)

### Community 3 - "django_db"
Cohesion: 0.03
Nodes (40): Migration, Migration, Migration, Migration, Migration, Migration, Migration, Migration (+32 more)

### Community 4 - "_make_movie"
Cohesion: 0.11
Nodes (6): DryRunImmutabilityTest, _guard_pass(), _make_movie(), _mock_tmdb_response(), QueueLifecycleAndProvenanceCorrectionTest, TMDBVerificationPipelineTest

### Community 5 - "router.tsx"
Cohesion: 0.08
Nodes (36): App(), AccountSettingsPage, AnimatedRoutes(), AppRouter(), AutoJoin, CreateSessionPage, DiscoverPage, EntryPage (+28 more)

### Community 6 - "GuestConversionValidationAndRejectionTests"
Cohesion: 0.07
Nodes (3): GuestConversionRecoverySecurityTests, GuestConversionSuccessTests, GuestConversionValidationAndRejectionTests

### Community 8 - "DiscoverPage.tsx"
Cohesion: 0.06
Nodes (31): Provider, ProviderLogo(), streamingCache, StreamingData, StreamingOptions(), ArchiveShelf, ArchiveShelfSection(), CatalogueSort (+23 more)

### Community 9 - "apiRequest"
Cohesion: 0.09
Nodes (39): 1. The `ApiError` Class, 2. Automatic Error Message Extraction, 3. Automatic Session Expiration Handling (401 Interceptor), 4. Empty States vs. Actual Errors, Frontend Error Handling (`api.ts` & React), AuthShell(), generateUsernameSuggestions(), getPasswordStrength() (+31 more)

### Community 11 - "tmdb_changes.py"
Cohesion: 0.06
Nodes (7): Command, poll_tmdb_changes(), PollerLockedError, RateLimitBackoffError, TmdbChangesService, TmdbConfigError, TmdbChangesServiceTests

### Community 12 - "LocalizedGenreRetrievalTests"
Cohesion: 0.09
Nodes (3): LocalizedGenreRetrievalTests, fake_ingest(), fake_ingest()

### Community 13 - "CinemaHeader"
Cohesion: 0.08
Nodes (40): BottomNav(), BottomNavProps, NavTab, CinemaHeader(), CinemaHeaderProps, useTheme(), AccountSettingsPage(), handleChangeEmail() (+32 more)

### Community 14 - "run_staleness_sweep"
Cohesion: 0.07
Nodes (5): Command, StalenessSweepCheckpoint, Meta, run_staleness_sweep(), StalenessSweepTests

### Community 17 - "IntelligenceWorkerProcess"
Cohesion: 0.06
Nodes (5): Command, IntelligenceWorkerProcess, _beat(), register_handler(), IntelligenceWorkerTasteHandlerTests

### Community 18 - "SessionPage.tsx"
Cohesion: 0.06
Nodes (52): DeckCardSkeleton(), MatchItemSkeleton(), MovieCardSkeleton(), ShelfSkeleton(), Skeleton(), SkeletonProps, StreamingItemSkeleton(), trackEvent() (+44 more)

### Community 19 - "compilerOptions"
Cohesion: 0.09
Nodes (21): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+13 more)

### Community 20 - "CatalogueJob"
Cohesion: 0.11
Nodes (9): reset_handlers(), CatalogueJob, JobType, Meta, Status, handle_full_reconciliation(), handle_sync_changes_feed(), to_json_safe() (+1 more)

### Community 22 - "WebSocketRevocationTests"
Cohesion: 0.08
Nodes (8): broadcast_credential_revocation(), WebSocketRevocationTests, run(), run(), run(), run(), run(), run()

### Community 23 - "ProposalExecutionWorker"
Cohesion: 0.07
Nodes (9): Command, ProposalOutboxMessage, Meta, ProposalOutboxMessageSerializer, Meta, ProposalExecutionWorker, ProposalLifecycleAndIdempotencyTestCase, ProposalOutboxWorkerTestCase (+1 more)

### Community 24 - "Pre1990ReleasePeriodFilterTests"
Cohesion: 0.04
Nodes (3): ClassicVaultEraFilterTests, Pre1990ReleasePeriodFilterTests, SwipeFailureRecoveryAndEdgeCaseTests

### Community 26 - "permissions.py"
Cohesion: 0.15
Nodes (4): configure_sqlite_pragmas(), CoreConfig, CoreConfig, IsOwner

### Community 27 - "transition_movie_classification"
Cohesion: 0.06
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

### Community 33 - "Systematic Debugging"
Cohesion: 0.12
Nodes (15): Do not use this skill when, Examples, First move, Guardrails, Inputs to gather, Outputs, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis (+7 more)

### Community 34 - "manifest.json"
Cohesion: 0.12
Nodes (16): background_color, categories, description, display, icons, lang, name, orientation (+8 more)

### Community 36 - "GuestProfile"
Cohesion: 0.07
Nodes (5): GuestActivityMiddleware, GuestProfile, Meta, GuestRecoveryConcurrencyTests, RecoveryHandoffReliabilityTests

### Community 37 - "UserPreferenceData"
Cohesion: 0.16
Nodes (3): MovieIntelligenceData, UserPreferenceData, ScoringServiceTestCase

### Community 40 - "backend/package.json"
Cohesion: 0.36
Nodes (7): devDependencies, autoprefixer@^10.4.23, postcss@^8.5.6, tailwindcss@^4.1.18, tailwindcss, autoprefixer, postcss

### Community 41 - "Genre"
Cohesion: 0.09
Nodes (8): Command, Command, Command, Genre, GenreSerializer, Meta, movie_genres_changed_handler(), register_eligibility_signals()

### Community 44 - "admin.py"
Cohesion: 0.20
Nodes (11): CustomUserAdmin, GenreAdmin, MatchAdmin, MovieAdmin, MovieStreamingAvailabilityAdmin, SessionAdmin, SessionStatsAdmin, StreamingProviderAdmin (+3 more)

### Community 47 - "views.py"
Cohesion: 0.02
Nodes (46): StandardResultsSetPagination, SwipeHistoryPagination, RegisterSerializer, Meta, AuthRateThrottle, GuestProvisionThrottle, GuestRecoverThrottle, PasswordResetRateThrottle (+38 more)

### Community 48 - ".link_guest_to_user"
Cohesion: 0.13
Nodes (6): DuplicateIdentityLinkError, IdentityLinkingService, _resolve_user_actor_ids(), IdentityLinkingServiceTests, Checkpoint 2: Reconciliation & Identity Complete, Phase 2: Reconciliation & Identity

### Community 49 - "enrichment_handlers.py"
Cohesion: 0.07
Nodes (14): Command, CatalogueQueueError, CatalogueQueueService, JobNotFoundError, StaleLeaseOwnershipError, acquire_tmdb_token(), check_deterministic_identity(), handle_catalogue_classification() (+6 more)

### Community 50 - ".agent/skills/ui-ux-pro-max/scripts/design_system.py"
Cohesion: 0.14
Nodes (8): _detect_page_type(), format_ascii_box(), format_markdown(), format_master_md(), format_page_override_md(), generate_design_system(), _generate_intelligent_overrides(), persist_design_system()

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

### Community 59 - "tmdb.py"
Cohesion: 0.06
Nodes (28): recalculate_movie_eligibility(), discover_movies(), _fetch(), fetch_cached_tmdb(), format_tmdb_movie(), get_enhanced_movie_details(), get_movie_by_tmdb_id(), _fetch() (+20 more)

### Community 61 - "evaluate_eligibility_predicates"
Cohesion: 0.08
Nodes (5): MovieQuerySet, evaluate_eligibility_predicates(), EligibilityPredicatesOptionBTests, MovieEligibilityModelAndSignalTests, MovieQuerySetRestrictionTests

### Community 62 - "tmdb_rate_limiter.py"
Cohesion: 0.15
Nodes (9): calculate_cooldown_with_jitter(), get_rate_limiter_status(), get_redis_client(), is_production(), record_tmdb_429(), _redis_eval_acquire(), _redis_eval_record_429(), _redis_eval_status() (+1 more)

### Community 64 - "TMDBTimeoutError"
Cohesion: 0.12
Nodes (6): get_movie_watch_providers(), TMDBAPIError, TMDBServiceError, TMDBTimeoutError, StreamingOptionsRemediationTests, MovieStreamingOptionsView

### Community 65 - "test_proposals.py"
Cohesion: 0.05
Nodes (19): CollaborativeAgreement, ConstraintExpansionProposal, Meta, ConstraintExpansionProposalSerializer, Meta, ProposalError, ProposalExpiredError, ProposalInvalidStateError (+11 more)

### Community 67 - "Session"
Cohesion: 0.07
Nodes (21): Session, SessionOccasionState, SessionStats, calculate_screening_affinity(), calculate_session_statistics(), calculate_taste_compatibility(), normalize_user_preferences(), ConflictingResponseError (+13 more)

### Community 69 - "partnerWaitingBehavior.test.tsx"
Cohesion: 0.13
Nodes (13): AvatarStack(), RecentSession, SessionCard(), SessionsListPage(), guestSessionResponse, hostSessionData, hostSessionResponse, mockApiRequest (+5 more)

### Community 71 - "test_batch5_personalization.py"
Cohesion: 0.06
Nodes (18): InteractionLog, Meta, UserTasteSignal, Meta, compute_cohort_divergence(), compute_negative_response_rate(), compute_preference_alignment(), compute_shelf_diversity() (+10 more)

### Community 72 - ".agent/skills/ui-ux-pro-max/scripts/core.py"
Cohesion: 0.06
Nodes (12): BM25, detect_domain(), _load_csv(), search(), _search_csv(), search_stack(), BM25, detect_domain() (+4 more)

### Community 73 - "_assert_safe_local_database"
Cohesion: 0.21
Nodes (5): _assert_safe_local_database(), _resolve_canonical_db_path(), SafetyGuardDebugFalseTest, SafetyGuardEngineTest, SafetyGuardPathTest

### Community 79 - "9. Practical Troubleshooting Playbook"
Cohesion: 0.12
Nodes (17): 10. `502 Bad Gateway`, 11. `503 Service Unavailable`, 12. `504 Gateway Timeout`, 13. `ConnectionResetError(54, 'Connection reset by peer')`, 14. `ECONNREFUSED 127.0.0.1:8000`, 15. `AbortError: The operation was aborted`, 16. `CatalogueJob status = failed_permanent`, 1. `200 55` (+9 more)

### Community 81 - "ArchiveShelvesService"
Cohesion: 0.10
Nodes (6): MovieSerializer, Meta, ArchiveShelvesService, CompleteCatalogueView, CuratorsSelectionView, YourArchiveView

### Community 84 - "ui-ux-pro-max"
Cohesion: 0.07
Nodes (29): Accessibility, Available Domains, Available Stacks, Common Rules for Professional UI, Example Workflow, How to Use This Skill, Icons & Visual Elements, Interaction (+21 more)

### Community 86 - "api.ts"
Cohesion: 0.16
Nodes (20): STEPS, RecoveryCodeModal(), RecoveryCodeModalProps, acknowledgeRecovery(), convertGuestAccount(), provisionGuest(), recoverGuest(), AuthUser (+12 more)

### Community 88 - "HardConstraints"
Cohesion: 0.07
Nodes (7): ActiveManifestImmutableError, ManifestCompilerService, ScoredCandidate, CandidatePool, HardConstraints, ManifestLearnedFeedbackIntegrationTests, ReproducibilityAndPersistenceTests

### Community 89 - "TmdbChangesCheckpoint"
Cohesion: 0.18
Nodes (3): TmdbChangesCheckpoint, Meta, PollTmdbChangesCommandTests

### Community 90 - "PasswordResetSecurityTests"
Cohesion: 0.07
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

### Community 96 - "set_redis_client"
Cohesion: 0.10
Nodes (3): set_redis_client(), TMDBRateLimiterProductionFailClosedTests, TMDBRateLimiterRedisLuaMockTests

### Community 97 - "DeckStateConcurrencyTests"
Cohesion: 0.18
Nodes (4): DeckStateConcurrencyTests, submit_duplicate(), submit_guest(), submit_host()

### Community 98 - "tests.py"
Cohesion: 0.02
Nodes (15): AuthenticationAndPermissionTests, ConcurrencyAndAtomicityTests, CoreUserExperienceRepairTests, GenreIntegrationTests, MotionAndSessionRegressionAuditTests, PaginationAndResourceLimitTests, RecentSessionsTests, RecommendationDiscoveryTests (+7 more)

### Community 99 - ".agent/skills/ui-ux-pro-max/scripts/search.py"
Cohesion: 0.11
Nodes (4): format_output(), format_output(), main(), start.sh script

### Community 106 - "7. Background Queue & Worker Numbers"
Cohesion: 0.40
Nodes (5): 7. Background Queue & Worker Numbers, Queue Priorities & Fair Scheduling Quotas, Retry Limits, Exponential Backoff & Quarantine, TMDB Dual-Bucket Rate Limiter Constants, Worker Leases, Fencing Tokens & Heartbeats

### Community 109 - "Phase6BatchCRecentSessionsAndStreamingTests"
Cohesion: 0.06
Nodes (10): Command, _make_session(), _tmdb_get(), fetch_tmdb_movies(), _create_tmdb_session(), get_tmdb_session(), reset_tmdb_session(), Phase6BatchCRecentSessionsAndStreamingTests (+2 more)

### Community 110 - "SessionDetailSerializer"
Cohesion: 0.09
Nodes (3): SessionDetailSerializer, Meta, SessionDetailView

### Community 112 - "StreamingProvider"
Cohesion: 0.08
Nodes (8): Command, Command, MovieStreamingAvailability, Meta, StreamingProvider, _link_streaming_availability(), resolve_streaming_provider_ids(), StreamingFilterAuditTests

### Community 114 - "SessionPage.tsx"
Cohesion: 0.06
Nodes (35): vitest@^5.1.0, ErrorBoundary, Props, State, ConstraintExhaustionNoticeModal(), ConstraintExhaustionNoticeModalProps, ConstraintProposalData, DecisionInfo (+27 more)

### Community 115 - "Workflow Phases (Summary)"
Cohesion: 0.25
Nodes (7): Common Rationalisations, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis, Phase 3: Hypothesis and Testing, Phase 4: Implementation, Phases, Red Flags, and Common Rationalisations, Workflow Phases (Summary)

### Community 116 - "Detailed Tasks"
Cohesion: 0.22
Nodes (8): Architecture & Data Decisions, Detailed Tasks, Implementation Plan: Batch 4 — Historical Interaction Reconciliation and Identity Linking, Risks and Mitigations, Task 4: Guest Identity Linking Service, Task 5: Durable Taste Engine Service & Job Handler, Task 7: Comprehensive Verification & PostgreSQL Concurrency Tests, Work Breakdown & Dependencies

### Community 130 - "middleware.py"
Cohesion: 0.13
Nodes (3): get_user_from_token_key(), TokenAuthMiddleware, TokenAuthMiddlewareStack()

### Community 133 - "2xx — Successful Responses"
Cohesion: 0.40
Nodes (5): 2xx — Successful Responses, HTTP 200 OK, HTTP 201 Created, HTTP 202 Accepted, HTTP 204 No Content

### Community 136 - "flick-frontend/package.json"
Cohesion: 0.05
Nodes (54): dependencies, canvas-confetti@^1.9.4, framer-motion@^12.31.0, lucide-react@^0.577.0, material-symbols@^0.40.2, posthog-js@^1.319.0, react@^19.2.0, react-dom@^19.2.0 (+46 more)

### Community 137 - "interface"
Cohesion: 0.33
Nodes (5): interface, display_name, short_description, policy, allow_implicit_invocation

### Community 139 - "Examples"
Cohesion: 0.40
Nodes (4): Example 1: Test failure with stack trace, Example 2: Intermittent test failure, Example 3: Regression after a commit, Examples

### Community 140 - "SwipeCreateView"
Cohesion: 0.15
Nodes (7): SessionChemistry, Meta, SwipeSerializer, Meta, _safe_analytics_callback(), SwipeCreateView, _update_analytics_after_commit()

### Community 141 - "Batch 4: Historical Interaction Reconciliation & Identity Linking — Task List"
Cohesion: 0.50
Nodes (3): Batch 4: Historical Interaction Reconciliation & Identity Linking — Task List, Checkpoint 3: Batch 4 Complete, Phase 3: Durable Taste Engine & Tombstone Anonymization

### Community 142 - "GuestRecoveryAPITests"
Cohesion: 0.06
Nodes (4): ExistingRegisteredUserCompatibilityTests, GuestProvisioningAPITests, GuestRecoveryAPITests, GuestThrottlingTests

### Community 144 - "PreferencesPage.tsx"
Cohesion: 0.14
Nodes (14): OptionIcon(), PreferencesPage(), buildPreferences(), checkSessionState(), handleNext(), handleSubmit(), loadAuthoritativeState(), Question (+6 more)

### Community 153 - "Match"
Cohesion: 0.06
Nodes (11): Match, Meta, WatchlistItem, Meta, EligibilityPolicyEngine, FilmNoirClassifier, HardConstraintFilter, WorldCinemaClassifier (+3 more)

### Community 167 - "4xx — Client-Side Errors"
Cohesion: 0.17
Nodes (12): 4xx — Client-Side Errors, HTTP 400 Bad Request, HTTP 401 Unauthorized, HTTP 403 Forbidden, HTTP 404 Not Found, HTTP 405 Method Not Allowed, HTTP 408 Request Timeout, HTTP 409 Conflict (+4 more)

### Community 172 - "DeckCardDeliveryView"
Cohesion: 0.22
Nodes (4): ManifestCompilationError, ReplenishmentInProgressError, TransientReplenishmentError, DeckCardDeliveryView

### Community 178 - "Flick — HTTP Status Codes, Server Logs & Error-Handling Reference"
Cohesion: 0.20
Nodes (9): 10. Glossary of Key Technical Terms, 1. Quick-Reference Cheat Sheet, 2. What Are HTTP Status Codes?, 8. Frontend & Build-Related Numbers, At a Glance: What Do These Numbers Mean?, Flick — HTTP Status Codes, Server Logs & Error-Handling Reference, Port Numbers, Table of Contents (+1 more)

### Community 179 - "CorrectSyntheticM1RecordsTest"
Cohesion: 0.16
Nodes (4): _resolve_staff_user(), _build_candidate_queryset(), CorrectSyntheticM1RecordsTest, _guard_pass()

### Community 180 - "verify-batch-b-browser.js"
Cohesion: 0.21
Nodes (5): puppeteer-core@^25.16.0, SCREENSHOT_DIR, SCREENSHOT_DIR, SCREENSHOT_DIR, puppeteer-core

### Community 197 - "5. Deep Dive: HTTP 304 Not Modified & Caching"
Cohesion: 0.40
Nodes (5): 5. Deep Dive: HTTP 304 Not Modified & Caching, Conditional Requests (ETag & Last-Modified), How Browser Caching Works, How Caching Is Implemented in Flick, When 304 Is Healthy vs When It Is a Problem

### Community 201 - ".reconcile"
Cohesion: 0.13
Nodes (3): Command, map_swipe_reaction(), reconcile_historical_interactions()

### Community 204 - "4. Deciphering Server Logs & Trailing Numbers"
Cohesion: 0.29
Nodes (7): 4. Deciphering Server Logs & Trailing Numbers, Anatomy of a Django/Daphne Access Log, What Do the Trailing Numbers Mean? (The 55 vs 1989 Mystery), Why does `/api/curators-selection/` show `200 1989`?, Why does `/api/users/profile/` show `200 55`?, Why does `GET /api/movies/` show `304 -` or `304 0`?, WSGI vs ASGI Logging Differences

### Community 205 - "test_indian_catalogue_ingestion.py"
Cohesion: 0.04
Nodes (9): validate_movie_language(), DiscoveryQuerySpec, IndianCatalogueCoverageReport, IndianCatalogueDiscoveryService, _ingest_tmdb_results(), LanguageValidationTests, TestIndianLanguageDiscovery, TestIngestionAndProvenance (+1 more)

### Community 211 - "InMemoryTokenBucket"
Cohesion: 0.15
Nodes (5): InMemoryTokenBucket, 1. The Movie Database (TMDB), 2. Redis, 3. PostgreSQL & SQLite, External Service Failure Modes (TMDB, Redis, Postgres)

### Community 219 - "test_observability_and_security.py"
Cohesion: 0.04
Nodes (19): CorrelationIdFilter, get_correlation_id(), reset_correlation_id(), SecretRedactionFilter, SecretRedactionFormatter, set_correlation_id(), CorrelationIdMiddleware, get_genres_map() (+11 more)

## Knowledge Gaps
- **91 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Movie` connect `Movie` to `Phase6BatchBBackendTests`, `SwipeAndMatchingTests`, `django_db`, `_make_movie`, `LimitValidationTest`, `Phase6BatchBConcurrencyTests`, `tmdb_changes.py`, `LocalizedGenreRetrievalTests`, `PreferenceAndManifestCorrectnessTests`, `run_staleness_sweep`, `Batch5PersonalizationEvaluationTests`, `DeckStateAPITests`, `IntelligenceWorkerProcess`, `DynamicMovieCatalogueTests`, `SwipeCreateView`, `CatalogueJob`, `Stage3EndToEndProductValidationTests`, `ProposalExecutionWorker`, `Pre1990ReleasePeriodFilterTests`, `Match`, `SessionLifecycleAndQuestionnaireRecoveryTests`, `transition_movie_classification`, `DiscoverTests`, `MatchListFilteringSecurityTests`, `RoomRecommendationScenariosTestCase`, `AffinityEvaluationTests`, `UserPreferenceData`, `HardConstraintFilter`, `Genre`, `UserProfile`, `admin.py`, `ScreeningSessionResultsAndStatsPersistenceTests`, `views.py`, `enrichment_handlers.py`, `CorrectSyntheticM1RecordsTest`, `Batch2EnrichmentAndWorkerTests`, `tmdb.py`, `evaluate_eligibility_predicates`, `TMDBTimeoutError`, `test_proposals.py`, `Session`, `Phase1EndToEndScenarioTestCase`, `test_batch5_personalization.py`, `test_indian_catalogue_ingestion.py`, `IntelligenceModelsTestCase`, `ArchiveShelvesService`, `SuperLikeReactionMatrixIntegrationTests`, `.anonymize_and_delete_user`, `HardConstraints`, `TmdbChangesCheckpoint`, `PostgreSQLQueueConcurrencyTests`, `._query_local_candidates`, `DeckStateConcurrencyTests`, `tests.py`, `BoutiqueManifestCompilationTests`, `SuperLikePersistenceAndAttributionTests`, `_validate_candidate`, `.from_movie`, `Phase6BatchCRecentSessionsAndStreamingTests`, `InteractionLogProcessingStatusTests`, `StreamingProvider`, `DatabaseConcurrencyAndSwipeReliabilityTests`, `.handle`, `rank_candidates_for_user`, `.classify_pool`, `.handle`, `NormalManifestCompilationTests`, `ShortageRedistributionAndFloorTests`?**
  _High betweenness centrality (0.244) - this node is a cross-community bridge._
- **Are the 130 inferred relationships involving `Movie` (e.g. with `Command` and `Command`) actually correct?**
  _`Movie` has 130 INFERRED edges - model-reasoned connections that need verification._
- **Should `Movie` be split into smaller, more focused modules?**
  _Cohesion score 0.0455820476858345 - nodes in this community are weakly interconnected._
- **Why does `6. Flick-Specific Error Handling Architecture` connect `6. Flick-Specific Error Handling Architecture` to `apiRequest`, `Flick — HTTP Status Codes, Server Logs & Error-Handling Reference`, `InMemoryTokenBucket`?**
  _High betweenness centrality (0.154) - this node is a cross-community bridge._
- **Are the 79 inferred relationships involving `Session` (e.g. with `MatchConsumer` and `SessionDetailSerializer`) actually correct?**
  _`Session` has 79 INFERRED edges - model-reasoned connections that need verification._
- **Should `Defense-in-Depth Debugging Strategies` be split into smaller, more focused modules?**
  _Cohesion score 0.06451612903225806 - nodes in this community are weakly interconnected._
- **Why does `Frontend Error Handling (`api.ts` & React)` connect `apiRequest` to `6. Flick-Specific Error Handling Architecture`?**
  _High betweenness centrality (0.153) - this node is a cross-community bridge._