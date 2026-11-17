---
updatedAt: 2026-04-20T20:26:21.000Z
agentTools:
  projectIndex: https://docs.wistia.com/llms.txt
---

# Show Background Job Status

Retrieves the status of a background job.

## Requires api token with one of the following permissions
```
Read all data
```

Tokens with the "Act with a team member's permissions" permission
(`all:delegate_to_contact_permissions` scope) can also be used. Requests
made with such a token are authorized using the permissions of the
contact assigned to the token.

An [expiring access token](https://docs.wistia.com/reference/post_expiring-token)
created with the `all:delegate_to_contact_permissions` scope can also be
used when its authorizations cover the record the job acts on: any
permission on that media, folder, channel or webinar suffices, and a job
on the account itself is covered by every token for that account. Jobs on
other records, including bulk operations, are not found.


# OpenAPI definition

````json
{
  "openapi": "3.1.1",
  "info": {
    "title": "Data API",
    "description": "Wistia Data API",
    "version": "2026.09.0"
  },
  "servers": [
    {
      "url": "https://api.wistia.com/modern"
    }
  ],
  "security": [
    {
      "BearerAuth": []
    }
  ],
  "tags": [
    {
      "name": "Background Job Status"
    }
  ],
  "paths": {
    "/background_job_status/{backgroundJobStatusId}": {
      "get": {
        "summary": "Show Background Job Status",
        "x-speakeasy-group": "backgroundJobStatus",
        "x-speakeasy-name-override": "get",
        "x-cli-topic-override": "jobs",
        "description": "Retrieves the status of a background job.\n\n## Requires api token with one of the following permissions\n```\nRead all data\n```\n\nTokens with the \"Act with a team member's permissions\" permission\n(`all:delegate_to_contact_permissions` scope) can also be used. Requests\nmade with such a token are authorized using the permissions of the\ncontact assigned to the token.\n\nAn [expiring access token](https://docs.wistia.com/reference/post_expiring-token)\ncreated with the `all:delegate_to_contact_permissions` scope can also be\nused when its authorizations cover the record the job acts on: any\npermission on that media, folder, channel or webinar suffices, and a job\non the account itself is covered by every token for that account. Jobs on\nother records, including bulk operations, are not found.\n",
        "parameters": [
          {
            "name": "backgroundJobStatusId",
            "in": "path",
            "description": "The hashed ID or numeric ID of the background job",
            "required": true,
            "schema": {
              "type": "string"
            }
          },
          {
            "name": "X-Wistia-API-Version",
            "in": "header",
            "required": true,
            "schema": {
              "type": "string",
              "default": "2026-09"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "OK",
            "content": {
              "application/json": {
                "schema": {
                  "unevaluatedProperties": false,
                  "type": "object",
                  "properties": {
                    "background_job_status": {
                      "unevaluatedProperties": false,
                      "allOf": [
                        {
                          "type": "object",
                          "description": "A background job keeps track of the progress of an asynchronous task, e.g\nbulk archiving media, translating media, etc.\n",
                          "properties": {
                            "id": {
                              "description": "The ID of the background job that's been queued for the request.",
                              "type": "integer"
                            },
                            "hashed_id": {
                              "description": "The unguessable hashed ID of the background job. Prefer this over the numeric ID when polling for status.",
                              "type": "string"
                            },
                            "status": {
                              "description": "The status of the background job that's been queued for the request.",
                              "type": "string",
                              "enum": [
                                "queued",
                                "started",
                                "finished",
                                "failed"
                              ]
                            }
                          },
                          "required": [
                            "id",
                            "hashed_id",
                            "status"
                          ]
                        },
                        {
                          "type": "object",
                          "properties": {
                            "object": {
                              "unevaluatedProperties": false,
                              "description": "The wrapped resource, present only when the job type carries typed\npoll content. Use `type` to discriminate which shape this is.\n",
                              "oneOf": [
                                {
                                  "type": "object",
                                  "description": "Wire view of a bulk operation as it appears inside a background job status\npoll response. Discriminated by `type`.\n",
                                  "unevaluatedProperties": false,
                                  "properties": {
                                    "type": {
                                      "type": "string",
                                      "description": "Discriminator identifying the wrapped resource type.",
                                      "enum": [
                                        "bulk_operation"
                                      ]
                                    },
                                    "summary": {
                                      "type": "object",
                                      "description": "Aggregate counts for the bulk operation. While the operation is\nrunning, `succeeded` and `failed` reflect progress so far.\n",
                                      "unevaluatedProperties": false,
                                      "properties": {
                                        "total": {
                                          "type": "integer",
                                          "description": "The total number of actions in the operation."
                                        },
                                        "succeeded": {
                                          "type": "integer",
                                          "description": "The number of actions that have completed successfully."
                                        },
                                        "failed": {
                                          "type": "integer",
                                          "description": "The number of actions that have failed."
                                        }
                                      },
                                      "required": [
                                        "total",
                                        "succeeded",
                                        "failed"
                                      ]
                                    },
                                    "results": {
                                      "type": "array",
                                      "description": "Per-action results, in submission order. Empty until actions begin\ncompleting.\n",
                                      "items": {
                                        "type": "object",
                                        "unevaluatedProperties": false,
                                        "properties": {
                                          "position": {
                                            "type": "integer",
                                            "description": "The zero-based index of the action within the submitted batch."
                                          },
                                          "operation": {
                                            "type": "string",
                                            "description": "The operation that was performed. `purchase` appears only for\noperations submitted through the Create Bulk Purchase endpoint.\n",
                                            "enum": [
                                              "create",
                                              "update",
                                              "delete",
                                              "move",
                                              "purchase"
                                            ]
                                          },
                                          "resource_type": {
                                            "type": "string",
                                            "description": "The type of resource the action operated on."
                                          },
                                          "id": {
                                            "type": "string",
                                            "description": "The hashed ID of the affected record. For successful creates this\nis the newly created record's ID. Absent when a create fails\nbefore a record exists.\n"
                                          },
                                          "status": {
                                            "type": "string",
                                            "description": "The outcome of the action.",
                                            "enum": [
                                              "succeeded",
                                              "failed"
                                            ]
                                          },
                                          "error": {
                                            "type": "string",
                                            "description": "The failure reason. Only present for failed actions."
                                          }
                                        },
                                        "required": [
                                          "position",
                                          "status"
                                        ]
                                      }
                                    }
                                  },
                                  "required": [
                                    "type",
                                    "summary",
                                    "results"
                                  ]
                                }
                              ]
                            }
                          }
                        }
                      ]
                    }
                  },
                  "required": [
                    "background_job_status"
                  ]
                }
              }
            }
          },
          "401": {
            "description": "Unauthorized, invalid or missing token",
            "content": {
              "application/json": {
                "schema": {
                  "unevaluatedProperties": false,
                  "type": "object",
                  "properties": {
                    "code": {
                      "description": "A machine-readable identifier for the specific authorization failure.",
                      "type": "string",
                      "enum": [
                        "unauthorized_credentials",
                        "account_inactive",
                        "unauthorized_scope",
                        "unauthorized_params"
                      ]
                    },
                    "error": {
                      "type": "string",
                      "examples": [
                        "Invalid credentials."
                      ]
                    }
                  }
                }
              }
            }
          },
          "404": {
            "description": "Resource not found"
          },
          "500": {
            "description": "Internal server error",
            "content": {
              "application/json": {
                "schema": {
                  "unevaluatedProperties": false,
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string",
                      "examples": [
                        "Internal server error"
                      ]
                    }
                  }
                }
              }
            }
          }
        },
        "tags": [
          "Background Job Status"
        ],
        "x-readme": {
          "code-samples": [
            {
              "name": "Typescript (SDK)",
              "language": "javascript",
              "code": "import { Wistia } from \"@wistia/wistia-api-client\";\n\nconst wistia = new Wistia({\n  bearerAuth: process.env[\"WISTIA_BEARER_AUTH\"] ?? \"\",\n});\n\nasync function run() {\n  const result = await wistia.backgroundJobStatus.get({\n    backgroundJobStatusId: \"108030\",\n  });\n\n  console.log(result);\n}\n\nrun();"
            }
          ]
        }
      }
    }
  },
  "components": {
    "securitySchemes": {
      "BearerAuth": {
        "type": "http",
        "scheme": "bearer"
      }
    }
  },
  "x-readme": {
    "samples-languages": [
      "javascript",
      "shell",
      "node",
      "python",
      "ruby"
    ]
  }
}
````