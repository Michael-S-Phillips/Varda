# Application Layer

The Application layer contains application-specific use cases and services. It orchestrates the flow of data between the presentation layer and the domain layer.

## Subdirectories

### project

Services for managing projects (e.g., ProjectContext).

### image

Services for managing images.

### roi

Services for managing regions of interest (e.g., ROIManager).

## Design Principles

1. **Dependency Rule**: The Application layer should not be depended upon by the Core layer. It may depend on the Core layer, but should not depend on the Infrastructure or Presentation layers.
2. **Separation of Concerns**: Each component in the Application layer should have a specific responsibility and should not be concerned with the responsibilities of other components.
3. **Interface Segregation**: Interfaces should be client-specific rather than general-purpose.
4. **Dependency Inversion**: High-level modules should not depend on low-level modules. Both should depend on abstractions.

## Usage Guidelines

When adding new components to the Application layer, consider the following guidelines:

1. **Use Cases**: Services that implement specific use cases of the application.
2. **Application Services**: Services that orchestrate the flow of data between the presentation layer and the domain layer.
3. **Interfaces**: Interfaces that define the contracts for infrastructure services.

When refactoring existing components, consider whether they are in the appropriate layer based on their responsibilities.