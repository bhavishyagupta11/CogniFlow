import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { router } from "./routes/router";
import { Toaster } from "sonner";
const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 5000,
            retry: 1,
        },
    },
});
export function App() {
    return (<QueryClientProvider client={queryClient}>
      <RouterProvider router={router}/>
      <Toaster position="top-right" richColors closeButton/>
    </QueryClientProvider>);
}
export default App;
