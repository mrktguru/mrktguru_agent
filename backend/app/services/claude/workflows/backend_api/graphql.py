from .._types import WorkflowDef, register

register(WorkflowDef(
    id="graphql_api",
    task_type="new_site",
    label="GraphQL API",
    keywords=["graphql", "apollo", "strawberry", "graphene", "hasura"],
    credits_min=2000,
    credits_max=3000,
    key_pause="после схемы типов и резолверов — подтверди Query/Mutation контракт",
    questionnaire=(
        "1. Сервер: Apollo Server, Strawberry (Python), Graphene, Hasura?\n"
        "2. БД и ORM?\n"
        "3. Subscriptions нужны (реалтайм)?\n"
        "4. Аутентификация: JWT, OAuth?\n"
        "5. Нужен ли DataLoader для N+1 проблем?"
    ),
    phases=(
        "1. Schema: типы, Query, Mutation (пауза)\n"
        "2. Резолверы + DataLoader\n"
        "3. Аутентификация + директивы авторизации\n"
        "4. Subscriptions (если нужны)\n"
        "5. GraphQL Playground / тесты"
    ),
    verification="GraphQL Playground → запросы и мутации работают; N+1 нет (DataLoader)",
    upsell=["Persisted queries", "Schema federation", "GraphQL Code Generator"],
    spec_hint="Зафиксируй: сервер, список типов, нужны ли subscriptions.",
))
