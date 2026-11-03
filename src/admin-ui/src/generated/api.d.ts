export interface paths {
    "/auth/exchange": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Consume an admin-issued, single-use login ticket; tickets expire in 5 minutes. Require same-origin requests. Return a session expiring in 8 hours; the cookie is HttpOnly, Secure, SameSite=Strict. Reusing an expired/consumed ticket returns 401. */
        post: operations["exchangeTicket"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Revoke the current session and clear its cookie. */
        post: operations["logout"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/telegram": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Validate signed Telegram initData (configured administrator, age <= 5 minutes, no future timestamp). Require same Origin. Return an 8-hour bearer token; store it only in memory. At most 5 valid exchanges per minute per running host; later exchanges return 429. No cookie is issued. */
        post: operations["exchangeTelegram"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/session": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Read the current session and recover its CSRF token after a page reload. */
        get: operations["getAdminSession"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/rollout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Read launch mode, revision and active-dialog count. Missing state defaults to admin-only. */
        get: operations["getRollout"];
        /** @description Set admin/all/off with expected_revision. All requires valid published menus and survey. Off stops new launches while existing sessions continue; no schema rollback is needed. */
        put: operations["setRollout"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/flows": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description List scenarios ordered by stable ID. */
        get: operations["listFlows"];
        put?: never;
        /** @description Create an unpublished scenario at draft revision 0; duplicate ID returns 409. */
        post: operations["createFlow"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/flows/{id}/versions/{version}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Read an immutable version for monitoring; editing uses the draft. */
        get: operations["getVersion"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/users/{user_id}/location": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Read the current or last observed user position without form data. */
        get: operations["getLocation"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/catalog": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Read allowed user-text templates from the current immutable catalog release and capability definitions. */
        get: operations["getEditorCatalog"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/texts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Read the editable user-text document, its optimistic-concurrency revision and current published release. */
        get: operations["getTextCatalog"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/texts/{key}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** @description Replace one draft text entry if expected_revision matches. The entry key must match the path. Editing the draft does not change published releases or active sessions. */
        put: operations["saveTextEntry"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/texts/publish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Validate all locales, themes, plural forms, placeholders and display limits, then publish an immutable catalog release at expected_revision. Existing scenario versions retain their pinned text release. */
        post: operations["publishTextCatalog"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/texts/releases": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description List immutable user-text release metadata without changing the draft or publication pointer. */
        get: operations["listTextCatalogReleases"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/texts/activate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Activate an existing text release if expected_current_release matches. Does not alter the draft, immutable scenario versions, active sessions or already rendered delivery intents. */
        post: operations["activateTextCatalog"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/flows/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Read draft and publication pointers. */
        get: operations["getFlow"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/flows/{id}/draft": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Read the editable document and its current revision. */
        get: operations["getDraft"];
        /** @description Replace a draft if expected_revision matches; increment its revision. document.id must match the path. Semantic errors may be saved for subsequent editing; structurally invalid documents return 422. Retrying with an old revision returns 409. */
        put: operations["saveDraft"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/flows/{id}/validate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Validate an unsaved document against registered contracts. Semantic issues return 200 with an issues list; malformed input returns 422. */
        post: operations["validateFlow"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/flows/{id}/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Simulate an unsaved scenario with supplied test data and delegate results. Never call live delegates or create user sessions. Missing stub results are reported as issues; no real data is fetched. An optional text_catalog_release selects a historical immutable text snapshot; omitted selects the current release. Rendered text uses the same resolver as Telegram. */
        post: operations["previewFlow"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/flows/{id}/publish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Validate and atomically publish the stored expected_revision. Repeating publication of that revision returns its original version without creating another. It does not reactivate an older version after rollback; use activate explicitly. Active sessions stay pinned. The new scenario version pins the catalog release used to validate it. */
        post: operations["publishFlow"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/flows/{id}/versions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description List immutable version metadata newest first. */
        get: operations["listVersions"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/flows/{id}/activate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Move the publication pointer to an existing version if expected_published_version matches. Does not migrate active sessions; incompatible delegate versions cannot be activated. A null expectation means the scenario has never been published. */
        post: operations["activateVersion"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/triggers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Read the trigger draft, revision and current immutable release. */
        get: operations["getTriggers"];
        /** @description Save a typed trigger draft with optimistic concurrency. Publication validates matchers and targets. */
        put: operations["saveTriggers"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/triggers/publish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Reject ambiguous/unsafe bindings and publish a manifest pinning scenario, delegate and text versions. Retries return the original release without reactivation. */
        post: operations["publishTriggers"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/triggers/releases": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description Read immutable trigger manifests newest first. */
        get: operations["listTriggerReleases"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/triggers/activate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Activate an immutable manifest with expected_current_release. Active sessions and displayed actions retain their pins. */
        post: operations["activateTriggers"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/delegates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description List available delegate contracts, not Python import paths or secrets. */
        get: operations["listDelegates"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/users/locations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description List registered users with runtime or last observed legacy positions ordered by user ID. Never return form answers or credentials. Unknown/lost legacy FSM states are marked explicitly. A sent screen does not imply it was read. */
        get: operations["listLocations"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/users/{user_id}/transitions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description List transition metadata newest first, without message text or field values. */
        get: operations["listTransitions"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** ActionNode */
        ActionNode: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "action";
            /** Id */
            id: string;
            /** Delegate */
            delegate: string;
            /**
             * Contract Version
             * @default 1
             */
            contract_version?: number;
            /** Arguments */
            arguments?: {
                [key: string]: components["schemas"]["LiteralValue"] | components["schemas"]["ReferenceValue"];
            };
            /** Results */
            results?: {
                [key: string]: string;
            };
            /** Outcomes */
            outcomes: {
                [key: string]: string;
            };
            /** Waiting Text */
            waiting_text?: (components["schemas"]["CatalogText"] | components["schemas"]["InlineText"])[];
        };
        /** ActionSnapshot */
        ActionSnapshot: {
            /** Template Id */
            template_id: string;
            /** Target */
            target: string;
            /** Assignments */
            assignments?: {
                [key: string]: components["schemas"]["DataValue"];
            };
            /** Item */
            item?: {
                [key: string]: components["schemas"]["DataValue"];
            };
        };
        /** ActivateTextCatalog */
        ActivateTextCatalog: {
            /** Release Id */
            release_id: number;
            /** Expected Current Release */
            expected_current_release: number;
        };
        /** ActivateVersion */
        ActivateVersion: {
            /** Version */
            version: number;
            /** Expected Published Version */
            expected_published_version: number | null;
        };
        /** AdminSession */
        AdminSession: {
            /** User Id */
            user_id: number;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Csrf Token */
            csrf_token: string;
        };
        /**
         * ApiError
         * @example {
         *       "code": "revision_conflict",
         *       "message": "The draft was changed; reload before saving.",
         *       "issues": []
         *     }
         * @example {
         *       "code": "invalid_flow",
         *       "message": "The scenario cannot be published.",
         *       "issues": [
         *         {
         *           "code": "missing_target",
         *           "path": "/nodes/0/buttons/0/0/target",
         *           "message": "Target does not exist",
         *           "node_id": "main",
         *           "button_id": "study"
         *         }
         *       ]
         *     }
         */
        ApiError: {
            /** Code */
            code: string;
            /** Message */
            message: string;
            /** Issues */
            issues?: components["schemas"]["ContractIssue"][];
        };
        /** Branch */
        Branch: {
            /** When */
            when: components["schemas"]["Compare"] | components["schemas"]["Exists"] | components["schemas"]["ConditionGroup"];
            /** Target */
            target: string;
        };
        /** ButtonEvent */
        ButtonEvent: {
            /** Update Id */
            update_id: number;
            /** User Id */
            user_id: number;
            /** Chat Id */
            chat_id: number;
            /** Session Id */
            session_id: string;
            /** Expected Revision */
            expected_revision: number;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "button";
            /** Button Id */
            button_id: string;
            /** @default null */
            snapshot?: components["schemas"]["ActionSnapshot"] | null;
        };
        /** CallNode */
        CallNode: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "call";
            /** Id */
            id: string;
            /** Flow */
            flow: string;
            /** Arguments */
            arguments?: {
                [key: string]: components["schemas"]["LiteralValue"] | components["schemas"]["ReferenceValue"];
            };
            /** Results */
            results?: {
                [key: string]: string;
            };
            /** Outcomes */
            outcomes: {
                [key: string]: string;
            };
        };
        /** CatalogTemplate */
        CatalogTemplate: {
            /** Key */
            key: string;
            /** Translations */
            translations: {
                [key: string]: string;
            };
            /** Themes */
            themes: {
                [key: string]: {
                    [key: string]: string;
                };
            };
        };
        /** CatalogText */
        CatalogText: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "catalog";
            /** Key */
            key: string;
            /** Parameters */
            parameters?: {
                [key: string]: components["schemas"]["LiteralValue"] | components["schemas"]["ReferenceValue"];
            };
        };
        /** Compare */
        Compare: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "compare";
            left: components["schemas"]["ReferenceValue"];
            /**
             * Operator
             * @enum {string}
             */
            operator: "eq" | "ne" | "in" | "lt" | "le" | "gt" | "ge";
            /** Right */
            right: (components["schemas"]["LiteralValue"] | components["schemas"]["ReferenceValue"]) | (string | boolean | number | null)[];
        };
        /** ConditionGroup */
        ConditionGroup: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "all" | "any";
            /** Conditions */
            conditions: (components["schemas"]["Compare"] | components["schemas"]["Exists"])[];
        };
        /** ConditionNode */
        ConditionNode: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "condition";
            /** Id */
            id: string;
            /** Branches */
            branches: components["schemas"]["Branch"][];
            /** Default */
            default: string;
        };
        /** ContactEvent */
        ContactEvent: {
            /** Update Id */
            update_id: number;
            /** User Id */
            user_id: number;
            /** Chat Id */
            chat_id: number;
            /** Session Id */
            session_id: string;
            /** Expected Revision */
            expected_revision: number;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "contact";
            /** Owner Id */
            owner_id: number | null;
            /** Phone */
            phone: string;
        };
        /** ContractIssue */
        ContractIssue: {
            /** Code */
            code: string;
            /** Path */
            path: string;
            /** Message */
            message: string;
            /**
             * Node Id
             * @default null
             */
            node_id?: string | null;
            /**
             * Button Id
             * @default null
             */
            button_id?: string | null;
        };
        /** DataField */
        DataField: {
            /**
             * Type
             * @enum {string}
             */
            type: "text" | "integer" | "number" | "boolean" | "list" | "object" | "secret";
            /**
             * Nullable
             * @default false
             */
            nullable?: boolean;
            /** @default null */
            items?: components["schemas"]["DataField"] | null;
            /** Properties */
            properties?: {
                [key: string]: components["schemas"]["DataField"];
            };
            /**
             * Max Items
             * @default 100
             */
            max_items?: number;
        };
        DataValue: string | boolean | number | components["schemas"]["DataValue"][] | {
            [key: string]: components["schemas"]["DataValue"];
        } | null;
        /** DelegateCatalog */
        DelegateCatalog: {
            /** Items */
            items: components["schemas"]["DelegateDefinition"][];
        };
        /** DelegateDefinition */
        DelegateDefinition: {
            /** Id */
            id: string;
            /**
             * Version
             * @default 1
             */
            version?: number;
            /**
             * Effect
             * @enum {string}
             */
            effect: "read" | "database_write" | "external";
            /** Inputs */
            inputs?: {
                [key: string]: components["schemas"]["DelegateParameter"];
            };
            /** Outputs */
            outputs?: {
                [key: string]: components["schemas"]["DataField"];
            };
            /** Outcomes */
            outcomes: string[];
        };
        /** DelegateParameter */
        DelegateParameter: {
            /**
             * Type
             * @enum {string}
             */
            type: "text" | "integer" | "number" | "boolean" | "list" | "object" | "secret";
            /**
             * Nullable
             * @default false
             */
            nullable?: boolean;
            /** @default null */
            items?: components["schemas"]["DataField"] | null;
            /** Properties */
            properties?: {
                [key: string]: components["schemas"]["DataField"];
            };
            /**
             * Max Items
             * @default 100
             */
            max_items?: number;
            /**
             * Required
             * @default true
             */
            required?: boolean;
        };
        /** DraftContent */
        DraftContent: {
            document: components["schemas"]["FlowDocument"];
        };
        /** EditorCatalog */
        EditorCatalog: {
            /** Texts */
            texts: components["schemas"]["CatalogTemplate"][];
            /** Capability Fields */
            capability_fields: {
                [key: string]: components["schemas"]["DataField"];
            };
            /** Capabilities */
            capabilities: {
                [key: string]: string | boolean | number | null;
            };
            /** Features */
            features?: components["schemas"]["FeatureOption"][];
            /**
             * Text Catalog Release
             * @default null
             */
            text_catalog_release?: number | null;
        };
        /** EndNode */
        EndNode: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "end";
            /** Id */
            id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "completed" | "cancelled" | "handed_off";
            /** Text */
            text?: (components["schemas"]["CatalogText"] | components["schemas"]["InlineText"])[];
            /**
             * Return Flow
             * @default null
             */
            return_flow?: string | null;
            /**
             * Feature
             * @default null
             */
            feature?: string | null;
        };
        /** ExchangeTelegram */
        ExchangeTelegram: {
            /** Init Data */
            init_data: string;
        };
        /** ExchangeTicket */
        ExchangeTicket: {
            /** Ticket */
            ticket: string;
        };
        /** Exists */
        Exists: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "exists";
            reference: components["schemas"]["ReferenceValue"];
        };
        /** FeatureOption */
        FeatureOption: {
            /** Id */
            id: string;
            /** Enabled */
            enabled: boolean;
        };
        /** FlowDocument */
        FlowDocument: {
            /**
             * Schema Version
             * @enum {integer}
             */
            schema_version: 1 | 2;
            /** Id */
            id: string;
            /** Entry */
            entry: string;
            /** Navigation Entries */
            navigation_entries?: {
                [key: string]: string;
            };
            /** Fields */
            fields?: {
                [key: string]: components["schemas"]["DataField"];
            };
            /** Inputs */
            inputs?: {
                [key: string]: components["schemas"]["DataField"];
            };
            /** Outputs */
            outputs?: {
                [key: string]: components["schemas"]["DataField"];
            };
            /** Outcomes */
            outcomes?: string[];
            /** Initial Data */
            initial_data?: {
                [key: string]: components["schemas"]["DataValue"];
            };
            /** Nodes */
            nodes: (components["schemas"]["MenuNode"] | components["schemas"]["InputNode"] | components["schemas"]["ConditionNode"] | components["schemas"]["ActionNode"] | components["schemas"]["EndNode"] | components["schemas"]["CallNode"] | components["schemas"]["ReturnNode"] | components["schemas"]["ReplaceNode"])[];
            /** Layout */
            layout?: {
                [key: string]: components["schemas"]["Position"];
            };
        };
        /** FlowDraft */
        FlowDraft: {
            document: components["schemas"]["FlowDocument"];
            /** Revision */
            revision: number;
        };
        /** FlowPage */
        FlowPage: {
            /** Items */
            items: components["schemas"]["FlowSummary"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** FlowSummary */
        FlowSummary: {
            /** Id */
            id: string;
            /** Draft Revision */
            draft_revision: number;
            /** Published Version */
            published_version: number | null;
        };
        /** FlowVersion */
        FlowVersion: {
            /** Flow Id */
            flow_id: string;
            /** Version */
            version: number;
            /** Draft Revision */
            draft_revision: number;
            /**
             * Published At
             * Format: date-time
             */
            published_at: string;
            /** Author Id */
            author_id: number;
            /**
             * Text Catalog Release
             * @default null
             */
            text_catalog_release?: number | null;
            /** Dependencies */
            dependencies?: {
                [key: string]: number;
            };
        };
        /** InlineText */
        InlineText: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "inline";
            /** Translations */
            translations: {
                [key: string]: string;
            };
            /** Themes */
            themes?: {
                [key: string]: {
                    [key: string]: string;
                };
            };
            /** Parameters */
            parameters?: {
                [key: string]: components["schemas"]["LiteralValue"] | components["schemas"]["ReferenceValue"];
            };
        };
        /** InputEvent */
        InputEvent: {
            /** Update Id */
            update_id: number;
            /** User Id */
            user_id: number;
            /** Chat Id */
            chat_id: number;
            /** Session Id */
            session_id: string;
            /** Expected Revision */
            expected_revision: number;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "input";
            /** Text */
            text: string;
        };
        /** InputNode */
        InputNode: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "input";
            /** Id */
            id: string;
            /** Text */
            text: (components["schemas"]["CatalogText"] | components["schemas"]["InlineText"])[];
            /** Field */
            field: string;
            /**
             * Input Type
             * @enum {string}
             */
            input_type: "text" | "integer" | "choice" | "contact" | "media" | "secret";
            /** Next */
            next: string;
            /** Error */
            error: components["schemas"]["CatalogText"] | components["schemas"]["InlineText"];
            /** Buttons */
            buttons?: (components["schemas"]["TransitionButton"] | components["schemas"]["UrlButton"])[][];
            /**
             * Min Length
             * @default 1
             */
            min_length?: number;
            /**
             * Max Length
             * @default 4000
             */
            max_length?: number;
            /**
             * Minimum
             * @default null
             */
            minimum?: number | null;
            /**
             * Maximum
             * @default null
             */
            maximum?: number | null;
            /** Choices */
            choices?: (string | boolean | number | null)[];
            /**
             * Multiple
             * @default false
             */
            multiple?: boolean;
            /** @default null */
            media?: components["schemas"]["ReferenceValue"] | null;
            /** Messages */
            messages?: (components["schemas"]["CatalogText"] | components["schemas"]["InlineText"])[];
            /** @default null */
            message_source?: components["schemas"]["ReferenceValue"] | null;
        };
        /** LegacyTarget */
        LegacyTarget: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "legacy";
            /** Adapter */
            adapter: string;
        };
        /** LiteralValue */
        LiteralValue: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "literal";
            value: components["schemas"]["DataValue"];
        };
        /** LocationPage */
        LocationPage: {
            /** Items */
            items: components["schemas"]["UserLocation"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** MediaEvent */
        MediaEvent: {
            /** Update Id */
            update_id: number;
            /** User Id */
            user_id: number;
            /** Chat Id */
            chat_id: number;
            /** Session Id */
            session_id: string;
            /** Expected Revision */
            expected_revision: number;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "media";
            /** Message Id */
            message_id: number;
            /**
             * Media Type
             * @enum {string}
             */
            media_type: "photo" | "video";
            /** File Id */
            file_id: string;
            /**
             * Media Group Id
             * @default null
             */
            media_group_id?: string | null;
            /**
             * Caption
             * @default null
             */
            caption?: string | null;
        };
        /** MenuNode */
        MenuNode: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "menu";
            /** Id */
            id: string;
            /** Text */
            text: (components["schemas"]["CatalogText"] | components["schemas"]["InlineText"])[];
            /**
             * Keyboard
             * @enum {string}
             */
            keyboard: "reply" | "inline";
            /** Buttons */
            buttons: (components["schemas"]["TransitionButton"] | components["schemas"]["UrlButton"])[][];
            /** Repeated */
            repeated?: components["schemas"]["RepeatedButtons"][];
            /** @default null */
            media?: components["schemas"]["ReferenceValue"] | null;
            /** Messages */
            messages?: (components["schemas"]["CatalogText"] | components["schemas"]["InlineText"])[];
            /** @default null */
            message_source?: components["schemas"]["ReferenceValue"] | null;
        };
        /** MiniAppSession */
        MiniAppSession: {
            /** User Id */
            user_id: number;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Access Token */
            access_token: string;
        };
        /** NavigationEvent */
        NavigationEvent: {
            /** Update Id */
            update_id: number;
            /** User Id */
            user_id: number;
            /** Chat Id */
            chat_id: number;
            /** Session Id */
            session_id: string;
            /** Expected Revision */
            expected_revision: number;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "navigation";
            /**
             * Action
             * @enum {string}
             */
            action: "main_menu" | "cancel" | "resume";
        };
        /** Position */
        Position: {
            /** X */
            x: number;
            /** Y */
            y: number;
        };
        /** PreviewButton */
        PreviewButton: {
            /** Id */
            id: string;
            /** Label */
            label: string;
            /**
             * Url
             * @default null
             */
            url?: string | null;
            /** @default null */
            snapshot?: components["schemas"]["ActionSnapshot"] | null;
        };
        /** PreviewDelegateResult */
        PreviewDelegateResult: {
            /** Outcome */
            outcome: string;
            /** Values */
            values?: {
                [key: string]: components["schemas"]["DataValue"];
            };
        };
        /** PreviewFrame */
        PreviewFrame: {
            /** Flow Id */
            flow_id: string;
            /** Flow Version */
            flow_version: number;
            /** Node Id */
            node_id: string;
            /** Data */
            data?: {
                [key: string]: components["schemas"]["DataValue"];
            };
            /**
             * Resume Status
             * @default null
             */
            resume_status?: ("waiting_button" | "waiting_input" | "waiting_effect") | null;
            /**
             * Revision
             * @default null
             */
            revision?: number | null;
            /**
             * Trigger Release
             * @default null
             */
            trigger_release?: number | null;
            /**
             * Effect Revision
             * @default null
             */
            effect_revision?: number | null;
        };
        /** PreviewPosition */
        PreviewPosition: {
            /** Flow Id */
            flow_id: string;
            /** Flow Version */
            flow_version: number;
            /** Node Id */
            node_id: string;
            /** Data */
            data?: {
                [key: string]: components["schemas"]["DataValue"];
            };
            /**
             * Resume Status
             * @default null
             */
            resume_status?: ("waiting_button" | "waiting_input" | "waiting_effect") | null;
            /**
             * Revision
             * @default null
             */
            revision?: number | null;
            /**
             * Trigger Release
             * @default null
             */
            trigger_release?: number | null;
            /**
             * Effect Revision
             * @default null
             */
            effect_revision?: number | null;
            /** Frames */
            frames?: components["schemas"]["PreviewFrame"][];
            /** Dependencies */
            dependencies?: {
                [key: string]: number;
            };
        };
        /** PreviewRequest */
        PreviewRequest: {
            document: components["schemas"]["FlowDocument"];
            /**
             * Node Id
             * @default null
             */
            node_id?: string | null;
            /** Data */
            data?: {
                [key: string]: components["schemas"]["DataValue"];
            };
            user: components["schemas"]["PreviewUser"];
            /** Eders Enabled */
            eders_enabled: boolean;
            /**
             * Event
             * @default null
             */
            event?: (components["schemas"]["ButtonEvent"] | components["schemas"]["InputEvent"] | components["schemas"]["ContactEvent"] | components["schemas"]["MediaEvent"] | components["schemas"]["SecretEvent"] | components["schemas"]["NavigationEvent"]) | null;
            /** Delegate Results */
            delegate_results?: {
                [key: string]: components["schemas"]["PreviewDelegateResult"];
            };
            /**
             * Text Catalog Release
             * @default null
             */
            text_catalog_release?: number | null;
            /** @default null */
            position?: components["schemas"]["PreviewPosition"] | null;
        };
        /** PreviewResult */
        PreviewResult: {
            /** Node Id */
            node_id: string;
            /** Data */
            data: {
                [key: string]: components["schemas"]["DataValue"];
            };
            screen: components["schemas"]["PreviewScreen"] | null;
            /** Issues */
            issues: components["schemas"]["ContractIssue"][];
            /** @default null */
            position?: components["schemas"]["PreviewPosition"] | null;
            /**
             * Node Kind
             * @default null
             */
            node_kind?: ("menu" | "input" | "end" | "return") | null;
        };
        /** PreviewScreen */
        PreviewScreen: {
            /** Text */
            text: string;
            /**
             * Keyboard
             * @enum {string}
             */
            keyboard: "reply" | "inline" | "none" | "main";
            /** Buttons */
            buttons: components["schemas"]["PreviewButton"][][];
            /**
             * Feature
             * @default null
             */
            feature?: string | null;
            /**
             * Return Flow
             * @default null
             */
            return_flow?: string | null;
            /** Messages */
            messages?: string[];
            /** Media */
            media?: components["schemas"]["ScreenMedia"][];
            /**
             * Contact Request
             * @default null
             */
            contact_request?: string | null;
            /**
             * Input Type
             * @default null
             */
            input_type?: ("text" | "integer" | "choice" | "contact" | "media" | "secret") | null;
        };
        /** PreviewUser */
        PreviewUser: {
            /** Id */
            id: number;
            /** Chat Id */
            chat_id: number;
            /**
             * Locale
             * @enum {string}
             */
            locale: "en" | "ru" | "ky" | "tr" | "zh";
            /**
             * Theme
             * @enum {string}
             */
            theme: "basic" | "halloween";
        };
        /** PublishDraft */
        PublishDraft: {
            /** Expected Revision */
            expected_revision: number;
        };
        /** ReferenceValue */
        ReferenceValue: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "ref";
            /**
             * Scope
             * @enum {string}
             */
            scope: "data" | "user" | "capabilities" | "item";
            /** Field */
            field: string;
            /** Path */
            path?: (string | number)[];
        };
        /** RepeatedButtons */
        RepeatedButtons: {
            source: components["schemas"]["ReferenceValue"];
            /** Buttons */
            buttons: (components["schemas"]["TransitionButton"] | components["schemas"]["UrlButton"])[];
        };
        /** ReplaceNode */
        ReplaceNode: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "replace";
            /** Id */
            id: string;
            /** Flow */
            flow: string;
            /** Arguments */
            arguments?: {
                [key: string]: components["schemas"]["LiteralValue"] | components["schemas"]["ReferenceValue"];
            };
        };
        /** ReturnNode */
        ReturnNode: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "return";
            /** Id */
            id: string;
            /** Outcome */
            outcome: string;
            /** Values */
            values?: {
                [key: string]: components["schemas"]["LiteralValue"] | components["schemas"]["ReferenceValue"];
            };
            /** Text */
            text?: (components["schemas"]["CatalogText"] | components["schemas"]["InlineText"])[];
        };
        /** RolloutStatus */
        RolloutStatus: {
            /**
             * Mode
             * @enum {string}
             */
            mode: "admin" | "all" | "off";
            /** Revision */
            revision: number;
            /** Active Dialogs */
            active_dialogs: number;
            /** Updated At */
            updated_at: string | null;
            /** Updated By */
            updated_by: number | null;
        };
        /** SaveDraft */
        SaveDraft: {
            document: components["schemas"]["FlowDocument"];
            /** Expected Revision */
            expected_revision: number;
        };
        /** SaveTextEntry */
        SaveTextEntry: {
            entry: components["schemas"]["TextEntry"];
            /** Expected Revision */
            expected_revision: number;
        };
        /** SaveTriggers */
        SaveTriggers: {
            document: components["schemas"]["TriggerDocument"];
            /** Expected Revision */
            expected_revision: number;
        };
        /** ScenarioPin */
        ScenarioPin: {
            /** Flow Id */
            flow_id: string;
            /** Version */
            version: number;
            /** Text Catalog Release */
            text_catalog_release: number;
        };
        /** ScenarioTarget */
        ScenarioTarget: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "scenario";
            /** Flow Id */
            flow_id: string;
            /**
             * Entry
             * @default null
             */
            entry?: string | null;
            /**
             * Navigation
             * @default null
             */
            navigation?: "study" | null;
            /** Arguments */
            arguments?: {
                [key: string]: "argument" | "actor_id" | "chat_id";
            };
        };
        /** ScreenMedia */
        ScreenMedia: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "photo" | "video";
            /** File Id */
            file_id: string;
            /**
             * Caption
             * @default null
             */
            caption?: string | null;
        };
        /** SecretEvent */
        SecretEvent: {
            /** Update Id */
            update_id: number;
            /** User Id */
            user_id: number;
            /** Chat Id */
            chat_id: number;
            /** Session Id */
            session_id: string;
            /** Expected Revision */
            expected_revision: number;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "secret";
            /** Handle */
            handle: string;
        };
        /** SetRollout */
        SetRollout: {
            /**
             * Mode
             * @enum {string}
             */
            mode: "admin" | "all" | "off";
            /** Expected Revision */
            expected_revision: number;
        };
        /** TextCatalogDraft */
        TextCatalogDraft: {
            document: components["schemas"]["TextDocument"];
            /** Revision */
            revision: number;
            /** Current Release */
            current_release: number;
        };
        /** TextCatalogRelease */
        TextCatalogRelease: {
            /** Id */
            id: number;
            /** Draft Revision */
            draft_revision: number;
            /**
             * Author Id
             * @default null
             */
            author_id?: number | null;
            /**
             * Published At
             * Format: date-time
             */
            published_at: string;
        };
        /** TextCatalogVersions */
        TextCatalogVersions: {
            /** Items */
            items: components["schemas"]["TextCatalogRelease"][];
        };
        /** TextDocument */
        TextDocument: {
            /**
             * Schema Version
             * @default 1
             * @constant
             */
            schema_version?: 1;
            /** Entries */
            entries: components["schemas"]["TextEntry"][];
        };
        /** TextEntry */
        TextEntry: {
            /** Key */
            key: string;
            /** Owner */
            owner: string;
            /**
             * Parameters
             * @default []
             */
            parameters?: string[];
            /**
             * Content Type
             * @enum {string}
             */
            content_type: "plain" | "html" | "label";
            /**
             * Plural Key
             * @default null
             */
            plural_key?: string | null;
            /** Variants */
            variants: components["schemas"]["TextVariant"][];
        };
        /** TextVariant */
        TextVariant: {
            /**
             * Locale
             * @enum {string}
             */
            locale: "en" | "ru" | "ky" | "tr" | "zh";
            /**
             * Theme
             * @enum {string}
             */
            theme: "basic" | "halloween";
            /**
             * Form
             * @enum {string}
             */
            form: "one" | "few" | "many" | "other";
            /** Text */
            text: string;
        };
        /** TransitionButton */
        TransitionButton: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "transition";
            /** Id */
            id: string;
            /** Label */
            label: components["schemas"]["CatalogText"] | components["schemas"]["InlineText"];
            /** Target */
            target: string;
            /** Assignments */
            assignments?: {
                [key: string]: components["schemas"]["LiteralValue"] | components["schemas"]["ReferenceValue"];
            };
            /**
             * When
             * @default null
             */
            when?: (components["schemas"]["Compare"] | components["schemas"]["Exists"] | components["schemas"]["ConditionGroup"]) | null;
        };
        /** TransitionPage */
        TransitionPage: {
            /** Items */
            items: components["schemas"]["UserTransition"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** TriggerBinding */
        TriggerBinding: {
            /** Id */
            id: string;
            matcher: components["schemas"]["TriggerMatcher"];
            /** Target */
            target: components["schemas"]["ScenarioTarget"] | components["schemas"]["LegacyTarget"];
            /**
             * Scope
             * @default private
             * @enum {string}
             */
            scope?: "private" | "group" | "any";
            /**
             * Access
             * @default public
             * @enum {string}
             */
            access?: "public" | "admin" | "moderation";
            /** Capabilities */
            capabilities?: string[];
            /**
             * Policy
             * @default reject_if_busy
             * @enum {string}
             */
            policy?: "reject_if_busy" | "resume" | "replace" | "preserve" | "call";
            /**
             * Fallback Adapter
             * @default null
             */
            fallback_adapter?: string | null;
        };
        /** TriggerDocument */
        TriggerDocument: {
            /**
             * Schema Version
             * @default 1
             * @constant
             */
            schema_version?: 1;
            /** Bindings */
            bindings: components["schemas"]["TriggerBinding"][];
        };
        /** TriggerDraftContent */
        TriggerDraftContent: {
            document: components["schemas"]["TriggerDocument"];
            /** Revision */
            revision: number;
            /** Current Release */
            current_release: number | null;
        };
        /** TriggerManifest */
        TriggerManifest: {
            document: components["schemas"]["TriggerDocument"];
            /** Scenarios */
            scenarios: components["schemas"]["ScenarioPin"][];
            /**
             * Text Catalog Release
             * @default 1
             */
            text_catalog_release?: number;
        };
        /** TriggerMatcher */
        TriggerMatcher: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "command" | "deep_link" | "prefix" | "callback" | "reply_label" | "native_reply";
            /** Key */
            key: string;
            /**
             * Arguments
             * @default none
             * @enum {string}
             */
            arguments?: "none" | "text" | "uuid" | "flow_id";
            /**
             * Action
             * @default null
             */
            action?: string | null;
        };
        /** TriggerReleaseContent */
        TriggerReleaseContent: {
            /** Id */
            id: number;
            /** Draft Revision */
            draft_revision: number;
            /** Author Id */
            author_id: number;
            /**
             * Published At
             * Format: date-time
             */
            published_at: string;
            manifest: components["schemas"]["TriggerManifest"];
        };
        /** TriggerVersions */
        TriggerVersions: {
            /** Items */
            items: components["schemas"]["TriggerReleaseContent"][];
        };
        /** UrlButton */
        UrlButton: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "url";
            /** Id */
            id: string;
            /** Label */
            label: components["schemas"]["CatalogText"] | components["schemas"]["InlineText"];
            /**
             * Url
             * Format: uri
             */
            url: string;
            /**
             * When
             * @default null
             */
            when?: (components["schemas"]["Compare"] | components["schemas"]["Exists"] | components["schemas"]["ConditionGroup"]) | null;
        };
        /** UserLocation */
        UserLocation: {
            /** User Id */
            user_id: number;
            /** Chat Id */
            chat_id: number;
            /**
             * Owner
             * @enum {string}
             */
            owner: "runtime" | "legacy" | "unknown";
            /** Flow Id */
            flow_id: string | null;
            /** Flow Version */
            flow_version: number | null;
            /** Node Id */
            node_id: string | null;
            /** Legacy State */
            legacy_state: string | null;
            /** Status */
            status: ("running" | "waiting_button" | "waiting_input" | "waiting_effect" | "completed" | "cancelled" | "handed_off" | "failed") | null;
            /** Delivery Status */
            delivery_status: ("pending" | "sent" | "failed" | "unknown") | null;
            /** Updated At */
            updated_at: string | null;
            /**
             * Handler
             * @default null
             */
            handler?: string | null;
        };
        /** UserTransition */
        UserTransition: {
            /** Id */
            id: number;
            /** Flow Id */
            flow_id: string | null;
            /** From Step */
            from_step: string | null;
            /** To Step */
            to_step: string | null;
            /** Outcome */
            outcome: string;
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            /**
             * Owner
             * @default unknown
             * @enum {string}
             */
            owner?: "runtime" | "legacy" | "unknown";
            /**
             * Flow Version
             * @default null
             */
            flow_version?: number | null;
        };
        /** ValidationReport */
        ValidationReport: {
            /** Issues */
            issues: components["schemas"]["ContractIssue"][];
        };
        /** VersionContent */
        VersionContent: {
            document: components["schemas"]["FlowDocument"];
            /** Version */
            version: number;
            /**
             * Text Catalog Release
             * @default null
             */
            text_catalog_release?: number | null;
            /** Dependencies */
            dependencies?: {
                [key: string]: number;
            };
        };
        /** VersionPage */
        VersionPage: {
            /** Items */
            items: components["schemas"]["FlowVersion"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    exchangeTicket: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExchangeTicket"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    /** @description Set or clear HttpOnly admin session cookie */
                    "Set-Cookie"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminSession"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    logout: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            204: {
                headers: {
                    /** @description Set or clear HttpOnly admin session cookie */
                    "Set-Cookie"?: string;
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    exchangeTelegram: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExchangeTelegram"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MiniAppSession"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Exchange limit */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    getAdminSession: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminSession"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    getRollout: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RolloutStatus"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    setRollout: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SetRollout"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RolloutStatus"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    listFlows: {
        parameters: {
            query?: {
                cursor?: string;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FlowPage"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    createFlow: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DraftContent"];
            };
        };
        responses: {
            /** @description Success */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FlowDraft"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    getVersion: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
                version: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VersionContent"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    getLocation: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserLocation"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    getEditorCatalog: {
        parameters: {
            query?: {
                /** @description Read the pinned text release for historical monitoring; default is the current release. */
                text_catalog_release?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EditorCatalog"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    getTextCatalog: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TextCatalogDraft"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    saveTextEntry: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                key: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SaveTextEntry"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TextCatalogDraft"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    publishTextCatalog: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PublishDraft"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TextCatalogRelease"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    listTextCatalogReleases: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TextCatalogVersions"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    activateTextCatalog: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ActivateTextCatalog"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TextCatalogDraft"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    getFlow: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FlowSummary"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    getDraft: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FlowDraft"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    saveDraft: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SaveDraft"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FlowDraft"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    validateFlow: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DraftContent"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ValidationReport"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    previewFlow: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PreviewRequest"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PreviewResult"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    publishFlow: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PublishDraft"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FlowVersion"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    listVersions: {
        parameters: {
            query?: {
                cursor?: string;
                limit?: number;
            };
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VersionPage"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    activateVersion: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ActivateVersion"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FlowSummary"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    getTriggers: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TriggerDraftContent"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    saveTriggers: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SaveTriggers"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TriggerDraftContent"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    publishTriggers: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PublishDraft"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TriggerReleaseContent"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    listTriggerReleases: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TriggerVersions"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    activateTriggers: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ActivateTextCatalog"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TriggerDraftContent"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    listDelegates: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DelegateCatalog"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    listLocations: {
        parameters: {
            query?: {
                cursor?: string;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LocationPage"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    listTransitions: {
        parameters: {
            query?: {
                cursor?: string;
                limit?: number;
            };
            header?: never;
            path: {
                user_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TransitionPage"];
                };
            };
            /** @description Authentication required */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Forbidden or CSRF check failed */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Resource not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Revision conflict or already exists */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Invalid request or scenario */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
}
