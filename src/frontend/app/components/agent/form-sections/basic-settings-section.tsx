"use client"

import { FormField, FormItem, FormLabel, FormControl, FormDescription, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea-fixed"
import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { HelpCircle, Plus, Trash, Bot } from "lucide-react"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import type { UseFormReturn } from "react-hook-form"
import type { z } from "zod"
import type { formSchema } from "../utils/form-schema"

type FormValues = z.infer<typeof formSchema>

interface BasicSettingsSectionProps {
  form: UseFormReturn<FormValues>
}

export default function BasicSettingsSection({ form }: BasicSettingsSectionProps) {
  const watchName = form.watch("name")

  // Generate agent ID from name
  function generateAgentId(name: string): string {
    // First convert to lowercase
    const lowercase = name.toLowerCase()
    // Then remove special characters (using a simpler regex)
    const noSpecialChars = lowercase.replace(/[^a-z0-9\s_]/g, "")
    // Finally replace spaces with underscores
    return noSpecialChars.replace(/\s+/g, "_")
  }

  const generatedId = watchName ? generateAgentId(watchName) : ""

  const addDefaultPrompt = () => {
    const currentPrompts = form.getValues("defaultPrompts")
    form.setValue("defaultPrompts", [...currentPrompts, ""])
  }

  const removeDefaultPrompt = (index: number) => {
    const currentPrompts = form.getValues("defaultPrompts")
    form.setValue(
      "defaultPrompts",
      currentPrompts.filter((_, i) => i !== index),
    )
  }

  return (
    <Card className="border-primary/20">
      <CardHeader className="bg-primary/5 rounded-t-lg">
        <CardTitle className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-primary" />
          Agent Information
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-6">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Agent Name</FormLabel>
              <FormControl>
                <Input placeholder="Data Analysis Agent" {...field} />
              </FormControl>
              <div className="flex justify-between">
                <FormDescription>The name of your agent. This will be displayed in the UI.</FormDescription>
                {watchName && (
                  <p className="text-xs text-muted-foreground mt-1">
                    ID: <span className="font-mono">{generatedId}</span>
                  </p>
                )}
              </div>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem className="mt-4">
              <FormLabel>Description</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="A brief description of what this agent does and how it can help users."
                  className="resize-none"
                  {...field}
                />
              </FormControl>
              <FormDescription>
                A short description that will be displayed on the agent page. Max 200 characters.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="systemPrompt"
          render={({ field }) => (
            <FormItem className="mt-4">
              <FormLabel className="flex items-center gap-2">
                System Prompt
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger type="button" onClick={(e) => e.preventDefault()} asChild>
                      <span className="cursor-help">
                        <HelpCircle className="h-4 w-4 text-muted-foreground" />
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="max-w-xs">
                        The system prompt defines the behavior and capabilities of your agent. It sets the context for
                        how the agent should respond to user inputs.
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </FormLabel>
              <FormControl>
                <Textarea
                  placeholder="You are a data analysis expert. Help users analyze and visualize their data."
                  className="min-h-[150px]"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-950/30 rounded-lg border border-blue-100 dark:border-blue-900">
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium flex items-center gap-2">
              <span className="text-blue-600 dark:text-blue-400">Example Prompts</span>
            </label>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={addDefaultPrompt}
              className="bg-white dark:bg-blue-900/50 border-blue-200 dark:border-blue-800 hover:bg-blue-50 dark:hover:bg-blue-900"
            >
              <Plus className="h-4 w-4 mr-1 text-blue-600 dark:text-blue-400" />
              Add Example Prompt
            </Button>
          </div>
          <p className="text-sm text-blue-700 dark:text-blue-300 mb-3">
            Example prompts that will be shown to users to help them get started.
          </p>

          {form.watch("defaultPrompts").map((_, index) => (
            <FormField
              key={index}
              control={form.control}
              name={`defaultPrompts.${index}`}
              render={({ field }) => (
                <FormItem className="mb-2 flex items-center gap-2">
                  <FormControl>
                    <Input
                      placeholder={`Example prompt ${index + 1}`}
                      {...field}
                      className="bg-white dark:bg-blue-900/30 border-blue-200 dark:border-blue-800"
                    />
                  </FormControl>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => removeDefaultPrompt(index)}
                    disabled={form.watch("defaultPrompts").length <= 1}
                    className="text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/50"
                  >
                    <Trash className="h-4 w-4" />
                  </Button>
                </FormItem>
              )}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
