---
updatedAt: 2026-04-20T20:26:21.000Z
agentTools:
  projectIndex: https://docs.wistia.com/llms.txt
---

# Swap Media

Swap one media with another media. This operation queues a background job to replace the original media with the replacement media while preserving the original media's hashed ID and URLs.

## Requires api token with one of the following permissions
```
Read, update & delete anything
```

Tokens with the "Act with a team member's permissions" permission
(`all:delegate_to_contact_permissions` scope) can also be used. Requests
made with such a token are authorized using the permissions of the
contact assigned to the token.

An [expiring access token](https://docs.wistia.com/reference/post_expiring-token)
created with the `all:delegate_to_contact_permissions` scope can also be
used when its authorizations grant the `update` permission on both the
media being replaced and the replacement media. A replacement media the
token does not name is treated as not found.


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
      "name": "Media"
    }
  ],
  "paths": {
    "/medias/{mediaHashedId}/swap": {
      "put": {
        "summary": "Swap Media",
        "x-speakeasy-group": "media",
        "x-speakeasy-name-override": "swap",
        "description": "Swap one media with another media. This operation queues a background job to replace the original media with the replacement media while preserving the original media's hashed ID and URLs.\n\n## Requires api token with one of the following permissions\n```\nRead, update & delete anything\n```\n\nTokens with the \"Act with a team member's permissions\" permission\n(`all:delegate_to_contact_permissions` scope) can also be used. Requests\nmade with such a token are authorized using the permissions of the\ncontact assigned to the token.\n\nAn [expiring access token](https://docs.wistia.com/reference/post_expiring-token)\ncreated with the `all:delegate_to_contact_permissions` scope can also be\nused when its authorizations grant the `update` permission on both the\nmedia being replaced and the replacement media. A replacement media the\ntoken does not name is treated as not found.\n",
        "parameters": [
          {
            "name": "mediaHashedId",
            "in": "path",
            "description": "The hashed ID of the media to be replaced.",
            "required": true,
            "schema": {
              "description": "Hashed ID of the media to be replaced.",
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
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "unevaluatedProperties": false,
                "type": "object",
                "properties": {
                  "replacement_media_id": {
                    "description": "The hashed ID of the media that will replace the original media. Must be the same media type as the original.",
                    "type": "string"
                  }
                },
                "required": [
                  "replacement_media_id"
                ]
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Successfully queued background job for media swap.",
            "content": {
              "application/json": {
                "schema": {
                  "unevaluatedProperties": false,
                  "allOf": [
                    {
                      "type": "object",
                      "properties": {
                        "message": {
                          "description": "A confirmation message that the background job has been queued.",
                          "type": "string"
                        },
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
                            }
                          ]
                        }
                      },
                      "required": [
                        "message",
                        "background_job_status"
                      ]
                    }
                  ],
                  "properties": {
                    "media": {
                      "unevaluatedProperties": false,
                      "allOf": [
                        {
                          "type": "object",
                          "description": "A media generally represents a video or an audio which can be embedded into your website.\n\nCDN-backed medias are accessible using this url structure: https://fast.wistia.com/embed/medias/{hashed_id}.m3u8.\nFor more information, see https://docs.wistia.com/docs/asset-urls#getting-hls-assets.\n",
                          "properties": {
                            "id": {
                              "description": "A unique numeric identifier for the media within the system.",
                              "type": "integer"
                            },
                            "name": {
                              "description": "The display name of the media.",
                              "type": "string"
                            },
                            "type": {
                              "description": "A string representing what type of media this is.",
                              "type": "string",
                              "enum": [
                                "Video",
                                "Audio",
                                "Image",
                                "PdfDocument",
                                "MicrosoftOfficeDocument",
                                "Swf",
                                "UnknownType"
                              ]
                            },
                            "archived": {
                              "description": "Whether or not the media is archived, either true or false.",
                              "type": "boolean"
                            },
                            "created": {
                              "description": "The date when the media was originally uploaded.",
                              "type": "string",
                              "format": "date-time"
                            },
                            "updated": {
                              "description": "The date when the media was last changed.",
                              "type": "string",
                              "format": "date-time"
                            },
                            "duration": {
                              "unevaluatedProperties": false,
                              "description": "Specifies the length (in seconds) for audio and video files. Specifies number of pages in the document. Omitted for other types of media.",
                              "oneOf": [
                                {
                                  "type": "number"
                                },
                                {
                                  "type": "null"
                                }
                              ]
                            },
                            "embedCode": {
                              "description": "DEPRECATED: If you want to programmatically embed videos, follow the construct an embed code guide.\n",
                              "type": "string",
                              "deprecated": true
                            },
                            "hashed_id": {
                              "description": "A unique alphanumeric identifier for this media.",
                              "type": "string"
                            },
                            "description": {
                              "description": "A description for the media which usually appears near the top of the sidebar on the media's page.",
                              "type": "string"
                            },
                            "progress": {
                              "description": "A floating point value between 0 and 1 that indicates the progress of the processing for this file.",
                              "type": "number",
                              "maximum": 1,
                              "minimum": 0
                            },
                            "status": {
                              "description": "Post upload processing status. - `queued`: the file is waiting in the queue to be processed. - `processing`: the file is actively being processed. - `ready`: the file has been fully processed and is ready for embedding and viewing. - `failed`: the file was unable to be processed (usually a format or size error).\n",
                              "type": "string",
                              "enum": [
                                "queued",
                                "processing",
                                "ready",
                                "failed"
                              ]
                            },
                            "section": {
                              "unevaluatedProperties": false,
                              "description": "The title of the section in which the media appears. This attribute is omitted if the media is not in a section (default).",
                              "oneOf": [
                                {
                                  "type": "string"
                                },
                                {
                                  "type": "null"
                                }
                              ]
                            },
                            "thumbnail": {
                              "unevaluatedProperties": false,
                              "type": "object",
                              "properties": {
                                "url": {
                                  "type": "string"
                                },
                                "width": {
                                  "type": "integer"
                                },
                                "height": {
                                  "type": "integer"
                                }
                              }
                            },
                            "protected": {
                              "description": "Whether the media is protected (e.g. requires a password or other authentication to view). Null if the media is not protected.",
                              "type": [
                                "boolean",
                                "null"
                              ]
                            }
                          }
                        }
                      ]
                    }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Bad request, e.g. missing replacement_media_id or media type mismatch.",
            "content": {
              "application/json": {
                "schema": {
                  "unevaluatedProperties": false,
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string",
                      "examples": [
                        "Replacement media must be the same type as the original media (Video)."
                      ]
                    }
                  }
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
          "403": {
            "description": "Forbidden, token is valid but account does not have access to feature",
            "content": {
              "application/json": {
                "schema": {
                  "unevaluatedProperties": false,
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string",
                      "examples": [
                        "Webinars are not available on your current plan"
                      ]
                    }
                  }
                }
              }
            }
          },
          "404": {
            "description": "Resource not found",
            "content": {
              "application/json": {
                "schema": {
                  "unevaluatedProperties": false,
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string",
                      "examples": [
                        "Folder with ID 'fakeid' not found."
                      ]
                    }
                  }
                }
              }
            }
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
          "Media"
        ],
        "x-readme": {
          "code-samples": [
            {
              "name": "Typescript (SDK)",
              "language": "javascript",
              "code": "import { Wistia } from \"@wistia/wistia-api-client\";\n\nconst wistia = new Wistia({\n  bearerAuth: process.env[\"WISTIA_BEARER_AUTH\"] ?? \"\",\n});\n\nasync function run() {\n  const result = await wistia.media.swap({\n    mediaHashedId: \"<id>\",\n  });\n\n  console.log(result);\n}\n\nrun();"
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