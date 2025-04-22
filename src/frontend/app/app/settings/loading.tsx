import { Skeleton } from "@/components/ui/skeleton"

export default function SettingsLoading() {
  return (
    <div className="flex h-full">
      {/* Left Navigation Menu Skeleton */}
      <div className="w-64 border-r bg-background h-full flex flex-col">
        <div className="p-4 border-b">
          <Skeleton className="h-4 w-32" />
        </div>
        <div className="p-2">
          {Array(5)
            .fill(0)
            .map((_, i) => (
              <Skeleton key={i} className="h-10 w-full mb-1 rounded-md" />
            ))}
        </div>
      </div>

      {/* Content Area Skeleton */}
      <div className="flex-1 p-6 overflow-auto">
        <Skeleton className="h-8 w-40 mb-6" />

        <div className="space-y-6">
          <div className="rounded-lg border">
            <div className="bg-muted p-4 rounded-t-lg">
              <Skeleton className="h-6 w-48" />
            </div>
            <div className="p-6 space-y-4">
              <div className="space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-4 w-64" />
              </div>

              <div className="space-y-2">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-24 w-full" />
                <Skeleton className="h-4 w-72" />
              </div>
            </div>
          </div>

          <div className="flex justify-end">
            <Skeleton className="h-10 w-32" />
          </div>
        </div>
      </div>
    </div>
  )
}
