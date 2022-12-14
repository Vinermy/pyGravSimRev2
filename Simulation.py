from typing import List

from Particle import Particle
from Vector2D import Vector2D
from json import load
from PIL import Image, ImageDraw
from PIL.ImageQt import ImageQt


class Simulation(object):
    def __init__(self, particles: List[Particle], framesize: tuple[int, int]) -> None:
        with open('config.json') as config: # Load the config file
            self.config = load(config)

        self.frameCounter = 0
        self.particles = particles
        self.framesize = framesize
        self.frameImage = Image.new("RGB", framesize, tuple(self.config["DRAWING"]["background_color"]))
        self.frameDraw = ImageDraw.Draw(self.frameImage)
        self.calculatedPositions = []
        self.positionLog = [[x.position for x in self.particles]]
        self.velocityLog = [[x.velocity.len() for x in self.particles]]
        self.accelerationLog = [[0 for x in self.particles]]
        self.maxVelocity = max(self.velocityLog[0])
        self.minVelocity = min(self.velocityLog[0])
        self.maxAcceleration = 0.
        self.minAcceleration = 0.

    def run_step(self,
                 draw_velocity_vectors: bool,
                 draw_barycenter: bool,
                 draw_trails: bool,
                 dependent_coloring: bool,
                 dependent_coloring_type: str) -> ImageQt:

        # Calculate accelerations for all particles
        self.velocityLog.append([]) # Add new rows for the data to be saved to
        self.accelerationLog.append([])
        for attracted in self.particles: # For every particle in the list...
            for attractor in self.particles: # For each other particle...
                distance: Vector2D = attractor.position - attracted.position # Get the distance between particles
                try:
                    acceleration = distance.stretch(attractor.mass / pow(distance.len(), 2)) # Calculate the acceleration
                    attracted.velocity += acceleration
                    attracted.acceleration = acceleration
                except ZeroDivisionError:
                    continue
            self.maxVelocity = max(self.maxVelocity, attracted.velocity.len()) # Update min/max values
            self.minVelocity = min(self.minVelocity, attracted.velocity.len())
            self.maxAcceleration = max(self.maxAcceleration, attracted.acceleration.len())
            self.minAcceleration = min(self.minAcceleration, attracted.acceleration.len())
            self.velocityLog[-1].append(attracted.velocity.len()) # Save the info about current step
            self.accelerationLog[-1].append(attracted.acceleration.len())
            self.calculatedPositions.append(attracted.position + attracted.velocity) # Save the calculated position

        for i in range(len(self.particles)): # Move particles
            self.particles[i].position = self.calculatedPositions[i]
        self.positionLog.append(self.calculatedPositions)
        self.calculatedPositions = []

        # Draw new frame
        self.frameDraw.rectangle(((0, 0), self.framesize),
                                 tuple(self.config["DRAWING"]["background_color"]))  # Clear the frame

        if draw_trails:
            for i in range(len(self.positionLog)): # For each body...
                if i == 0:
                    continue
                for j in range(len(self.positionLog[i])): # Draw the line between it's position on every consecutive frames
                    self.frameDraw.line(xy=((self.positionLog[i][j].x + self.framesize[0] // 2,
                                             self.positionLog[i][j].y + self.framesize[0] // 2),
                                            (self.positionLog[i - 1][j].x + self.framesize[0] // 2,
                                             self.positionLog[i - 1][j].y + self.framesize[0] // 2)),
                                        fill=tuple(map(lambda x: min(int(x * pow(self.config["DRAWING"]["trails_fade"], # Make the trail fade over time
                                                                                 len(self.positionLog) - i)), 255),
                                                       self.config["DRAWING"]["trail_color"])))

        for particle in self.particles:
            if dependent_coloring:
                match dependent_coloring_type:
                    case "velocity":
                        interpolated_velocity = translate(particle.velocity.len(), self.minVelocity, self.maxVelocity) # Interpolate the velocity to 0-1 range
                        c1 = self.config["DRAWING"]["velocity_gradient_color_0"]
                        c2 = self.config["DRAWING"]["velocity_gradient_color_1"]
                        color = [0, 0, 0]
                        for comp in range(3):
                            color[comp] = int(c1[comp] + interpolated_velocity * (c2[comp] - c1[comp])) # Interpolate the velocity between every component of c1 and c2
                    case "acceleration":
                        interpolated_acceleration = translate(particle.acceleration.len(), # The same procedure, but with the acceleration
                                                              self.minAcceleration,
                                                              self.maxAcceleration)
                        c1 = self.config["DRAWING"]["acceleration_gradient_color_0"]
                        c2 = self.config["DRAWING"]["acceleration_gradient_color_1"]
                        color = [0, 0, 0]
                        for comp in range(3):
                            color[comp] = int(c1[comp] + interpolated_acceleration * (c2[comp] - c1[comp]))
                    case _:
                        color = self.config["DRAWING"]["particle_color"] # In case dependent_coloring_type does not fall into one of the cases just use the default color
            else:
                color = self.config["DRAWING"]["particle_color"]

            pos: Vector2D = Vector2D(self.framesize[0] // 2, self.framesize[1] // 2) + particle.position # Translate the particle coordinates to the frame's coordinate system
            self.frameDraw.ellipse(xy=((pos.x - particle.radius, # Draw the particle
                                        pos.y - particle.radius),
                                       (pos.x + particle.radius,
                                        pos.y + particle.radius)),
                                   fill=tuple(color))

            self.frameDraw.text((pos.x, # Render it's id
                                 pos.y),
                                str(particle.id),
                                fill=tuple(self.config["DRAWING"]["particle_label_color"]))

            if draw_velocity_vectors:
                self.frameDraw.line(xy=((pos.x, pos.y), # Draw the line between particle's position on this frame and the next frame assuming that velocity does not change
                                        (pos.x + particle.velocity.x * (self.config["DRAWING"]["vel_vect_multiplier"]), # multiply the velocity, so the line is easier to be seen
                                         pos.y + particle.velocity.y * (
                                             self.config["DRAWING"]["vel_vect_multiplier"]))),
                                    fill=tuple(self.config["DRAWING"]["velocity_vectors_color"]))

            if draw_barycenter:
                barycenter_position: Vector2D = sum([particle.position * particle.mass for particle in self.particles], #Find the average position weighted by mass
                                                    Vector2D(0, 0)) / sum(
                    [particle.mass for particle in self.particles])
                barycenter_position = Vector2D(self.framesize[0] // 2, self.framesize[1] // 2) + barycenter_position # Translate to frame's coordinate system
                self.frameDraw.ellipse(xy=(barycenter_position.x - 5,
                                           barycenter_position.y - 5,
                                           barycenter_position.x + 5,
                                           barycenter_position.y + 5),
                                       fill=tuple(self.config["DRAWING"]["barycenter_color"])) # Draw the barycenter at that coordinates

        return ImageQt(self.frameImage) # Return the frame image

    def draw_force_heatmap(self) -> ImageQt:
        # Calculate the force applied to every pixel of the frame
        min_force = 1000000
        max_force = -1
        field = [0] * self.framesize[0] * self.framesize[1]
        for i in range(self.framesize[0]):
            for j in range(self.framesize[1]):
                forces = []
                for body in self.particles:
                    distance = body.position - Vector2D(i, j) + Vector2D(self.framesize[0] // 2, self.framesize[1] // 2)
                    try:
                        forces.append(
                            distance.stretch(body.mass / pow(max(distance.len(), body.radius), 2))
                        )
                    except ZeroDivisionError:
                        pass
                force = sum(forces, Vector2D(0, 0)).len()
                field[i * self.framesize[1] + j] = force
                min_force = min(min_force, force)
                max_force = max(max_force, force)

        # Map all the values to a range from 0 to 1
        field = list(map(lambda x: translate(x, min_force, max_force) ** 0.2, field))

        # Color the pixels:
        for i in range(self.framesize[0] * self.framesize[1]):

            c1 = self.config["DRAWING"]["heatmap_gradient_color_0"]
            c2 = self.config["DRAWING"]["heatmap_gradient_color_1"]
            color = [0, 0, 0]
            for component in range(3):
                color[component] = int(
                    c1[component] + (field[i] * (c2[component] - c1[component]))
                )
            self.frameImage.putpixel(xy=(i // self.framesize[0],
                                         i % self.framesize[1]), value=tuple(color))

        return ImageQt(self.frameImage)


def translate(value, Min, Max):
    # Figure out how 'wide' each range is
    span = Max - Min

    # Convert the left range into a 0-1 range (float)
    value_scaled = float(value - Min) / float(span)

    return value_scaled
