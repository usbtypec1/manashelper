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
        /** @description Read allowed gettext templates and capability definitions. */
        get: operations["getEditorCatalog"];
        put?: never;
        post?: never;
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
        /** @description Simulate an unsaved scenario with supplied test data and delegate results. Never call live delegates or create user sessions. Missing stub results are reported as issues; no real data is fetched. Rendered text uses the same safe formatting rules as Telegram. */
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
        /** @description Validate and atomically publish the stored expected_revision. Repeating publication of that revision returns its original version without creating another. It does not reactivate an older version after rollback; use activate explicitly. Active sessions stay pinned. */
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
            type: "text" | "integer" | "number" | "boolean";
            /**
             * Nullable
             * @default false
             */
            nullable?: boolean;
        };
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
            effect: "read" | "database_write";
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
            type: "text" | "integer" | "number" | "boolean";
            /**
             * Nullable
             * @default false
             */
            nullable?: boolean;
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
             * @constant
             */
            schema_version: 1;
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
            /** Initial Data */
            initial_data?: {
                [key: string]: string | boolean | number | null;
            };
            /** Nodes */
            nodes: (components["schemas"]["MenuNode"] | components["schemas"]["InputNode"] | components["schemas"]["ConditionNode"] | components["schemas"]["ActionNode"] | components["schemas"]["EndNode"])[];
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
            input_type: "text" | "integer" | "choice";
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
        };
        /** LiteralValue */
        LiteralValue: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "literal";
            /** Value */
            value: string | boolean | number | null;
        };
        /** LocationPage */
        LocationPage: {
            /** Items */
            items: components["schemas"]["UserLocation"][];
            /** Next Cursor */
            next_cursor: string | null;
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
        };
        /** PreviewDelegateResult */
        PreviewDelegateResult: {
            /** Outcome */
            outcome: string;
            /** Values */
            values?: {
                [key: string]: string | boolean | number | null;
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
                [key: string]: string | boolean | number | null;
            };
            user: components["schemas"]["PreviewUser"];
            /** Eders Enabled */
            eders_enabled: boolean;
            /**
             * Event
             * @default null
             */
            event?: (components["schemas"]["ButtonEvent"] | components["schemas"]["InputEvent"] | components["schemas"]["NavigationEvent"]) | null;
            /** Delegate Results */
            delegate_results?: {
                [key: string]: components["schemas"]["PreviewDelegateResult"];
            };
        };
        /** PreviewResult */
        PreviewResult: {
            /** Node Id */
            node_id: string;
            /** Data */
            data: {
                [key: string]: string | boolean | number | null;
            };
            screen: components["schemas"]["PreviewScreen"] | null;
            /** Issues */
            issues: components["schemas"]["ContractIssue"][];
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
            scope: "data" | "user" | "capabilities";
            /** Field */
            field: string;
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
            status: ("running" | "waiting_button" | "waiting_input" | "completed" | "cancelled" | "handed_off" | "failed") | null;
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
