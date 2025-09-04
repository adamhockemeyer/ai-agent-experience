"use client"

import { FormField, FormItem, FormLabel, FormControl, FormDescription } from "@/components/ui/form"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Bot, AlertTriangle, CheckCircle, XCircle } from "lucide-react"
import { useEffect, useState } from "react"
import type { UseFormReturn } from "react-hook-form"
import type { AgentFormValues } from "../utils/form-utils"

interface AdvancedSettingsSectionProps {
  form: UseFormReturn<AgentFormValues>
}

export default function AdvancedSettingsSection({ form }: AdvancedSettingsSectionProps) {
  const enableHistoryReduction = form.watch("enableHistoryReduction")
  const requireJsonResponse = form.watch("requireJsonResponse")
  const agentType = form.watch("agentType")
  const isChatCompletionAgent = agentType === "ChatCompletionAgent"

  // JSON schema validation state
  const [jsonSchemaError, setJsonSchemaError] = useState<string | null>(null)
  const [isValidJsonSchema, setIsValidJsonSchema] = useState<boolean>(true)

  // Function to validate JSON schema
  const validateJsonSchema = (schema: string): { isValid: boolean; error: string | null } => {
    if (!schema || schema.trim() === "") {
      return { isValid: true, error: null } // Empty is allowed
    }

    try {
      const parsed = JSON.parse(schema)

      // Basic validation for structured outputs requirements
      if (typeof parsed !== 'object' || parsed === null) {
        return { isValid: false, error: "Schema must be a JSON object" }
      }

      if (parsed.type !== 'object') {
        return { isValid: false, error: "Root schema type must be 'object'" }
      }

      if (!parsed.properties || typeof parsed.properties !== 'object') {
        return { isValid: false, error: "Schema must have 'properties' field" }
      }

      if (!parsed.required || !Array.isArray(parsed.required)) {
        return { isValid: false, error: "Schema must have 'required' array with all property names" }
      }

      if (parsed.additionalProperties !== false) {
        return { isValid: false, error: "Schema must have 'additionalProperties: false'" }
      }

      // Check that all properties are in required array
      const propertyNames = Object.keys(parsed.properties)
      const missingRequired = propertyNames.filter(prop => !parsed.required.includes(prop))
      if (missingRequired.length > 0) {
        return {
          isValid: false,
          error: `All properties must be required. Missing: ${missingRequired.join(', ')}`
        }
      }

      // Check for nested objects and their required fields
      for (const [propName, propDef] of Object.entries(parsed.properties)) {
        if (typeof propDef === 'object' && propDef !== null && (propDef as any).type === 'object') {
          const nestedObj = propDef as any
          if (nestedObj.properties && !nestedObj.required) {
            return {
              isValid: false,
              error: `Nested object '${propName}' must have 'required' array`
            }
          }
          if (nestedObj.properties && nestedObj.required) {
            const nestedProps = Object.keys(nestedObj.properties)
            const missingNested = nestedProps.filter((prop: string) => !nestedObj.required.includes(prop))
            if (missingNested.length > 0) {
              return {
                isValid: false,
                error: `Nested object '${propName}' missing required fields: ${missingNested.join(', ')}`
              }
            }
          }
          if (nestedObj.additionalProperties !== false) {
            return {
              isValid: false,
              error: `Nested object '${propName}' must have 'additionalProperties: false'`
            }
          }
        }
      }

      return { isValid: true, error: null }
    } catch (e) {
      return { isValid: false, error: "Invalid JSON format" }
    }
  }

  // Default JSON schema for structured outputs
  const defaultJsonSchema = `{
  "type": "object",
  "properties": {
    "answer": {
      "type": "string",
      "description": "The main response to the user's question"
    },
    "reasoning": {
      "type": "string", 
      "description": "Step-by-step reasoning that led to this answer"
    },
    "confidence": {
      "type": "number",
      "minimum": 0,
      "maximum": 1,
      "description": "Confidence score between 0 and 1"
    },
    "sources": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "List of sources or references used"
    }
  },
  "required": ["answer", "reasoning", "confidence", "sources"],
  "additionalProperties": false
}`

  // Reset settings when agent type is not ChatCompletionAgent
  useEffect(() => {
    if (!isChatCompletionAgent) {
      if (enableHistoryReduction) {
        form.setValue("enableHistoryReduction", false)
      }
      if (requireJsonResponse) {
        form.setValue("requireJsonResponse", false)
      }
    }
  }, [isChatCompletionAgent, enableHistoryReduction, requireJsonResponse, form])

  // Set default JSON schema when JSON response is enabled and no schema exists
  useEffect(() => {
    if (requireJsonResponse && isChatCompletionAgent) {
      const currentSchema = form.getValues("jsonResponseSchema")
      if (!currentSchema || currentSchema.trim() === "") {
        form.setValue("jsonResponseSchema", defaultJsonSchema)
      }
    }
  }, [requireJsonResponse, isChatCompletionAgent, form, defaultJsonSchema])

  // Validate JSON schema in real-time
  useEffect(() => {
    const subscription = form.watch((value, { name }) => {
      if (name === "jsonResponseSchema") {
        const schemaValue = value.jsonResponseSchema || ""
        const validation = validateJsonSchema(schemaValue)
        setIsValidJsonSchema(validation.isValid)
        setJsonSchemaError(validation.error)
      }
    })

    // Initial validation
    const currentSchema = form.getValues("jsonResponseSchema")
    if (currentSchema) {
      const validation = validateJsonSchema(currentSchema)
      setIsValidJsonSchema(validation.isValid)
      setJsonSchemaError(validation.error)
    }

    return () => subscription.unsubscribe()
  }, [form, validateJsonSchema])

  return (
    <Card className="border-gray-200 dark:border-gray-800">
      <CardHeader className="bg-gray-50 dark:bg-gray-900/50 rounded-t-lg">
        <CardTitle className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-gray-600 dark:text-gray-400" />
          Advanced Settings
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-6 space-y-4">
        <FormField
          control={form.control}
          name="requireJsonResponse"
          render={({ field }) => (
            <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4 bg-gray-50/50 dark:bg-gray-900/20">
              <div className="space-y-0.5">
                <FormLabel className="text-base">Require JSON Response</FormLabel>
                <FormDescription>
                  {isChatCompletionAgent
                    ? "Require the agent to respond with structured JSON according to a schema."
                    : "Structured JSON responses are only available for Chat Completion Agents."
                  }
                </FormDescription>
              </div>
              <FormControl>
                <Switch
                  checked={field.value}
                  onCheckedChange={field.onChange}
                  disabled={!isChatCompletionAgent}
                />
              </FormControl>
            </FormItem>
          )}
        />

        {requireJsonResponse && isChatCompletionAgent && (
          <div className="p-4 bg-blue-50/50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
            <FormField
              control={form.control}
              name="jsonResponseSchema"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="flex items-center gap-2">
                    JSON Response Schema
                    {field.value && field.value.trim() !== "" ? (
                      isValidJsonSchema ? (
                        <CheckCircle className="h-4 w-4 text-green-500" />
                      ) : (
                        <XCircle className="h-4 w-4 text-red-500" />
                      )
                    ) : (
                      <AlertTriangle className="h-4 w-4 text-orange-500" />
                    )}
                  </FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Enter JSON schema..."
                      className={`min-h-[200px] font-mono text-sm ${field.value && field.value.trim() !== "" && !isValidJsonSchema
                          ? "border-red-500 focus:border-red-500 focus:ring-red-500"
                          : field.value && field.value.trim() !== "" && isValidJsonSchema
                            ? "border-green-500 focus:border-green-500 focus:ring-green-500"
                            : ""
                        }`}
                      {...field}
                      value={field.value || ""}
                    />
                  </FormControl>
                  {jsonSchemaError && (
                    <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 p-2 rounded border border-red-200 dark:border-red-800">
                      <div className="flex items-center gap-2">
                        <XCircle className="h-4 w-4" />
                        <span className="font-medium">Schema Error:</span>
                      </div>
                      <p className="mt-1">{jsonSchemaError}</p>
                    </div>
                  )}
                  <FormDescription>
                    Define the JSON schema that the agent must follow in its responses.
                    This enforces structured output format and validates responses against the schema.
                    <br />
                    <span className="text-xs text-muted-foreground mt-1 block">
                      Requirements: Must be an object with "required" array containing all property names, and "additionalProperties: false"
                    </span>
                  </FormDescription>
                </FormItem>
              )}
            />
          </div>
        )}

        <FormField
          control={form.control}
          name="enableHistoryReduction"
          render={({ field }) => (
            <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4 bg-gray-50/50 dark:bg-gray-900/20">
              <div className="space-y-0.5">
                <FormLabel className="text-base">Enable Chat History Reduction</FormLabel>
                <FormDescription>
                  {isChatCompletionAgent
                    ? "Automatically summarize and reduce chat history to manage long conversations efficiently."
                    : "Chat history reduction is only available for Chat Completion Agents."
                  }
                </FormDescription>
              </div>
              <FormControl>
                <Switch
                  checked={field.value}
                  onCheckedChange={field.onChange}
                  disabled={!isChatCompletionAgent}
                />
              </FormControl>
            </FormItem>
          )}
        />

        {enableHistoryReduction && isChatCompletionAgent && (
          <div className="grid grid-cols-2 gap-4 p-4 bg-blue-50/50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
            <FormField
              control={form.control}
              name="reducerMsgCount"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Message Count</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      placeholder="10"
                      {...field}
                      onChange={(e) => field.onChange(parseInt(e.target.value) || 10)}
                    />
                  </FormControl>
                  <FormDescription>Target number of messages to retain after reduction</FormDescription>
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="reducerThreshold"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Threshold</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      placeholder="10"
                      {...field}
                      onChange={(e) => field.onChange(parseInt(e.target.value) || 10)}
                    />
                  </FormControl>
                  <FormDescription>Buffer to prevent premature reduction</FormDescription>
                </FormItem>
              )}
            />
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export { AdvancedSettingsSection }
