# OpenAPI

The handlers already say what the API is. `OpenApi` writes that down as an OpenAPI 3.1 document so you don't keep a second copy.

```cpp
app.attach(OpenApi{{.title = "Orders", .version = "1.4.0", .docs = "/docs"}});
```

`GET /openapi.json` serves the document for every HTTP route, built at ignite from the handlers. `GET /docs` is an interactive page. That page loads Swagger UI from `cdn.jsdelivr.net`. If your content security policy only allows your own origin, leave `.docs` unset and serve the JSON yourself. gRPC methods are left out. Their contract is the `.proto`. `/__routes` is left out too.

## What lands in the document

| In the handler | In the document |
|---|---|
| `{id}` and its parameter's type | A required path parameter, with the integer's range when it has one |
| `Query<T>` | One query parameter per member, required unless optional or defaulted |
| `Header<"x-tenant">` | A header parameter, required unless optional |
| `Json<T>` | A required `application/json` body, plus 415 and 422 responses |
| `Auth<>` | A bearer security requirement, and a 401 |
| `T`, `Json<T>`, `std::string`, `NoContent`, `Created<T>`, `std::optional<T>`, `Result<T>`, `Cacheable<T>`, `Task<T>` | The success response. 404 for an optional, 304 for a cacheable |
| Any failure | `default`: `application/problem+json` with the shared `Problem` schema |

Structs become schemas in `components/schemas`, following exactly what `Json<T>` reads and writes: renames, `as_string`, time formats, enums as their names, maps, recursion, untagged variants (`anyOf`), and `json::tag` variants (`oneOf` with a discriminator). Validation annotations become JSON Schema keywords (`minimum`, `maxLength`, `minItems`, `pattern`, `format: email`). `json::from_path` members are `readOnly`. A member is `required` when a request must send it. Two structs with the same name get qualified names (`billing.Order`).

Each operation uses the handler's name as `operationId` (`shop.create_order`), its scope as the tag, and a summary from the function name. `Auth` records the bearer scheme. `auth::require` and `auth::any_of` add `x-required-roles` and `x-required-roles-match` (`all` or `any`), plus a 403.

## Writing it at build time

To print the document instead of serving it:

```cpp
if (argc > 1 && argv[1] == "--openapi"sv) {
  std::cout << crocket::openapi_document(app, {.title = "Orders", .version = "1.4.0"});
  return 0;
}
```

The same function is what the fairing serves. Nothing is written twice, so the document can't drift from the signatures.
